"""종목명/종목코드 → DART corp_code 매핑.

DART corpCode.xml(zip)을 내려받아 상장사만 인메모리 테이블로 유지한다 (주 1회 갱신, 설계 §4).
"""

import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

import httpx

from why_moved.cache.store import TTLCache
from why_moved.common.errors import StockNotFoundError, UpstreamError

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
CORP_CODE_TTL = 7 * 86400  # 주 1회


@dataclass(frozen=True)
class Corp:
    corp_code: str   # DART 고유번호 (8자리)
    stock_code: str  # 거래소 종목코드 (6자리)
    name: str


class CorpCodeResolver:
    def __init__(self, api_key: str, cache: TTLCache, timeout: float = 30.0):
        self._api_key = api_key
        self._cache = cache
        self._timeout = timeout
        self._by_name: dict[str, Corp] = {}
        self._by_stock_code: dict[str, Corp] = {}

    async def _load(self) -> None:
        if self._by_name:
            return
        rows = self._cache.get("corp_codes:listed")
        if rows is None:
            rows = await self._fetch_rows()
            self._cache.set("corp_codes:listed", rows, CORP_CODE_TTL)
        corps = [Corp(*row) for row in rows]
        self._by_name = {c.name: c for c in corps}
        self._by_stock_code = {c.stock_code: c for c in corps}

    async def _fetch_rows(self) -> list[list[str]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(CORP_CODE_URL, params={"crtfc_key": self._api_key})
                resp.raise_for_status()
                content = resp.content
        except httpx.HTTPError as exc:
            raise UpstreamError("DART(corpCode)", str(exc)) from exc

        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml_bytes = zf.read(zf.namelist()[0])
        root = ET.fromstring(xml_bytes)
        rows = []
        for el in root.iter("list"):
            stock_code = (el.findtext("stock_code") or "").strip()
            if len(stock_code) != 6:  # 비상장 제외
                continue
            rows.append([
                (el.findtext("corp_code") or "").strip(),
                stock_code,
                (el.findtext("corp_name") or "").strip(),
            ])
        return rows

    async def name_map(self) -> dict[str, str]:
        """종목코드 → 종목명 매핑 (스크리너 조인용)."""
        await self._load()
        return {code: corp.name for code, corp in self._by_stock_code.items()}

    async def resolve(self, query: str) -> Corp:
        """종목명 또는 6자리 종목코드로 상장사를 찾는다."""
        await self._load()
        q = query.strip()
        if q.isdigit() and len(q) == 6:
            corp = self._by_stock_code.get(q)
            if corp:
                return corp
            raise StockNotFoundError(query)
        corp = self._by_name.get(q)
        if corp:
            return corp
        # 부분일치 폴백: 유일하게 매칭될 때만 허용 (오답 방지)
        candidates = [c for name, c in self._by_name.items() if q in name]
        if len(candidates) == 1:
            return candidates[0]
        raise StockNotFoundError(query)
