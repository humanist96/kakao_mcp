"""DART OpenAPI 어댑터.

https://opendart.fss.or.kr — 무료 키, 일 20,000건 한도(설계 §4) → 캐시 필수.
"""

from typing import Any

import httpx

from why_moved.cache.store import TTLCache
from why_moved.common.errors import UpstreamError

BASE_URL = "https://opendart.fss.or.kr/api"

# DART pblntf_ty 코드: A=정기공시 B=주요사항보고 C=발행공시 D=지분공시 I=거래소공시
DISCLOSURE_LIST_TTL = 600          # 10분 (설계 §4)
COMPANY_TTL = 86400                # 24시간
FINANCIALS_TTL = 86400             # 24시간
OWNERSHIP_TTL = 3600               # 1시간


class DartClient:
    def __init__(self, api_key: str, cache: TTLCache, timeout: float = 5.0):
        self._api_key = api_key
        self._cache = cache
        self._timeout = timeout

    async def _get(self, path: str, params: dict[str, Any], ttl: float, cache_key: str) -> dict:
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{BASE_URL}/{path}",
                    params={"crtfc_key": self._api_key, **params},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise UpstreamError("DART", str(exc)) from exc

        # status 000=정상, 013=조회 결과 없음 (없음은 정상 흐름으로 취급)
        if data.get("status") not in ("000", "013"):
            raise UpstreamError("DART", f"status={data.get('status')} {data.get('message', '')}")
        self._cache.set(cache_key, data, ttl)
        return data

    async def search_disclosures(
        self,
        corp_code: str | None = None,
        bgn_de: str = "",
        end_de: str = "",
        pblntf_ty: str = "",
        page_count: int = 100,
    ) -> list[dict]:
        """공시검색. 반환: [{rcept_no, corp_name, report_nm, rcept_dt, ...}]"""
        params: dict[str, Any] = {"page_count": page_count}
        if corp_code:
            params["corp_code"] = corp_code
        if bgn_de:
            params["bgn_de"] = bgn_de
        if end_de:
            params["end_de"] = end_de
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty
        key = f"dart:list:{corp_code}:{bgn_de}:{end_de}:{pblntf_ty}:{page_count}"
        data = await self._get("list.json", params, DISCLOSURE_LIST_TTL, key)
        return data.get("list", [])

    async def get_company(self, corp_code: str) -> dict:
        """기업개황."""
        return await self._get(
            "company.json", {"corp_code": corp_code}, COMPANY_TTL, f"dart:company:{corp_code}"
        )

    async def get_financials(self, corp_code: str, bsns_year: str, reprt_code: str) -> list[dict]:
        """단일회사 전체 재무제표 (XBRL).

        reprt_code: 11013=1분기 11012=반기 11014=3분기 11011=사업보고서
        """
        key = f"dart:fin:{corp_code}:{bsns_year}:{reprt_code}"
        data = await self._get(
            "fnlttSinglAcntAll.json",
            {"corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code, "fs_div": "CFS"},
            FINANCIALS_TTL,
            key,
        )
        rows = data.get("list", [])
        if rows:
            return rows
        # 연결(CFS) 미제출 기업은 별도(OFS)로 폴백
        key_ofs = f"{key}:ofs"
        data = await self._get(
            "fnlttSinglAcntAll.json",
            {"corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code, "fs_div": "OFS"},
            FINANCIALS_TTL,
            key_ofs,
        )
        return data.get("list", [])

    async def get_executive_holdings(self, corp_code: str) -> list[dict]:
        """임원·주요주주 소유상황 보고 (내부자 매매). rcept_dt는 YYYYMMDD로 정규화."""
        key = f"dart:elestock:{corp_code}"
        data = await self._get("elestock.json", {"corp_code": corp_code}, OWNERSHIP_TTL, key)
        return _normalize_dates(data.get("list", []))

    async def get_major_holdings(self, corp_code: str) -> list[dict]:
        """5% 대량보유 보고. rcept_dt는 YYYYMMDD로 정규화."""
        key = f"dart:majorstock:{corp_code}"
        data = await self._get("majorstock.json", {"corp_code": corp_code}, OWNERSHIP_TTL, key)
        return _normalize_dates(data.get("list", []))


def _normalize_dates(rows: list[dict]) -> list[dict]:
    """지분공시 API는 rcept_dt를 '2024-08-01' 형식으로 준다 — YYYYMMDD로 통일한 새 목록 반환."""
    return [
        {**row, "rcept_dt": str(row.get("rcept_dt", "")).replace("-", "")}
        for row in rows
    ]
