"""DART fnlttSinglAcntAll 응답에서 핵심 계정을 추출한다."""

_ACCOUNT_ALIASES = {
    "revenue": ("매출액", "수익(매출액)", "영업수익"),
    "operating_income": ("영업이익", "영업이익(손실)", "영업손익"),
    "net_income": ("당기순이익", "당기순이익(손실)", "당기순손익"),
    "equity": ("자본총계",),
    "liabilities": ("부채총계",),
    "capital": ("자본금",),
}


def _to_number(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(str(raw).replace(",", ""))
    except ValueError:
        return None


def extract_financials(rows: list[dict]) -> dict[str, float | None]:
    """당기/전기 핵심 계정 추출.

    반환 키: revenue, operating_income, net_income, equity, liabilities, capital,
             prev_revenue, prev_operating_income
    """
    result: dict[str, float | None] = {
        "revenue": None, "operating_income": None, "net_income": None,
        "equity": None, "liabilities": None, "capital": None,
        "prev_revenue": None, "prev_operating_income": None,
    }
    for row in rows:
        account = (row.get("account_nm") or "").strip()
        for field, aliases in _ACCOUNT_ALIASES.items():
            if account not in aliases or result[field] is not None:
                continue
            # 손익 계정은 손익계산서(IS/CIS), 재무상태 계정은 BS만 취한다
            sj_div = row.get("sj_div", "")
            is_income_field = field in ("revenue", "operating_income", "net_income")
            if is_income_field and sj_div not in ("IS", "CIS"):
                continue
            if not is_income_field and sj_div != "BS":
                continue
            result[field] = _to_number(row.get("thstrm_amount"))
            if field == "revenue":
                result["prev_revenue"] = _to_number(row.get("frmtrm_amount"))
            if field == "operating_income":
                result["prev_operating_income"] = _to_number(row.get("frmtrm_amount"))
    return result
