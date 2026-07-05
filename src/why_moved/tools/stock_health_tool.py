"""stock_health — 종목 건강진단 (설계 §2.4)."""

from dataclasses import asdict
from datetime import datetime

from why_moved.common.envelope import envelope, source
from why_moved.context import AppContext
from why_moved.engine.financial_extract import extract_financials
from why_moved.engine.health_score import (
    FinancialSnapshot,
    axis_scores,
    narrative,
    overall_grade,
    run_checks,
)

_ANNUAL_REPORT = "11011"


async def stock_health(ctx: AppContext, query: str) -> dict:
    corp = await ctx.resolver.resolve(query)

    fiscal_year, fin = await _latest_annual(ctx, corp.corp_code)
    valuation = await ctx.market.get_fundamental(corp.stock_code)

    snapshot = FinancialSnapshot(
        revenue=fin.get("revenue"),
        operating_income=fin.get("operating_income"),
        net_income=fin.get("net_income"),
        equity=fin.get("equity"),
        liabilities=fin.get("liabilities"),
        prev_revenue=fin.get("prev_revenue"),
        prev_operating_income=fin.get("prev_operating_income"),
        per=valuation.get("per"),
        pbr=valuation.get("pbr"),
        div_yield=valuation.get("div"),
    )
    checks = run_checks(snapshot)
    scores = axis_scores(snapshot)
    grade = overall_grade(scores)

    payload = {
        "stock": {"name": corp.name, "code": corp.stock_code},
        "scores": scores,
        "grade": grade,
        "narrative": narrative(checks, grade),
        "checks": [asdict(c) for c in checks],
        "data_basis": {
            "fiscal_period": f"{fiscal_year}년 사업보고서" if fiscal_year else "재무 데이터 없음",
            "valuation_note": "PER·PBR·배당수익률은 네이버 금융 최근 거래일 기준이에요.",
        },
    }
    sources = [
        source("DART 재무제표", "https://dart.fss.or.kr", fiscal_year or ""),
        source("네이버 금융 밸류에이션", f"https://m.stock.naver.com/domestic/stock/{corp.stock_code}"),
    ]
    return envelope(payload, sources)


async def _latest_annual(ctx: AppContext, corp_code: str) -> tuple[str, dict]:
    """가장 최근에 제출된 사업보고서 재무를 찾는다 (당해→전년 순서로 시도)."""
    current_year = datetime.now().year
    for year in (current_year - 1, current_year - 2):
        try:
            rows = await ctx.dart.get_financials(corp_code, str(year), _ANNUAL_REPORT)
        except Exception:
            continue
        if rows:
            return str(year), extract_financials(rows)
    return "", {}
