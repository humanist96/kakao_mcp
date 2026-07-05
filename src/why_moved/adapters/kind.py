"""KIND(거래소 공시) 어댑터 — 관리종목·불성실공시법인 목록.

KIND는 공식 API가 없어 best-effort로 조회하며, 실패 시 룰 평가에서
"확인 불가"로 우아하게 강등된다 (설계 §2.2: 크래시 금지).
"""

import httpx

from why_moved.cache.store import TTLCache

KIND_TTL = 86400  # 일 1회 (설계 §4)

_ENDPOINTS = {
    # KIND 투자유의 안내 화면의 목록 조회 (POST form)
    "managed": {
        "url": "https://kind.krx.co.kr/investwarn/adminissue.do",
        "data": {"method": "searchAdminIssueSub", "currentPageSize": "3000", "pageIndex": "1"},
    },
    "unfaithful": {
        "url": "https://kind.krx.co.kr/investwarn/unfaithdesignate.do",
        "data": {"method": "searchUnfaithDesignateSub", "currentPageSize": "3000", "pageIndex": "1"},
    },
}


class KindClient:
    def __init__(self, cache: TTLCache, timeout: float = 5.0):
        self._cache = cache
        self._timeout = timeout

    async def _fetch_codes(self, kind: str) -> list[str] | None:
        """해당 목록에 오른 종목코드 목록. 조회 실패 시 None (확인 불가)."""
        key = f"kind:{kind}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                ep = _ENDPOINTS[kind]
                resp = await client.post(ep["url"], data=ep["data"])
                resp.raise_for_status()
                codes = _extract_stock_codes(resp.text)
        except httpx.HTTPError:
            return None
        self._cache.set(key, codes, KIND_TTL)
        return codes

    async def is_managed(self, stock_code: str) -> bool | None:
        """관리종목 여부. None = 확인 불가."""
        codes = await self._fetch_codes("managed")
        return None if codes is None else stock_code in codes

    async def is_unfaithful(self, stock_code: str) -> bool | None:
        """불성실공시법인 여부. None = 확인 불가."""
        codes = await self._fetch_codes("unfaithful")
        return None if codes is None else stock_code in codes


def _extract_stock_codes(html: str) -> list[str]:
    """KIND 응답 HTML에서 6자리 종목코드를 추출한다."""
    import re

    # KIND 목록은 onclick="companysummary_open('005930')" 패턴으로 코드를 노출한다
    codes = re.findall(r"companysummary_open\('(\d{6})'\)", html)
    if not codes:
        codes = re.findall(r"isuCd=(\d{6})", html)
    return sorted(set(codes))
