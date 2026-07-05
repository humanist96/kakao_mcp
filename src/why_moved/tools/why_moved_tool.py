"""[Hero #1] why_moved — 종목 급등락 원인 설명 (설계 §2.1)."""

from datetime import datetime, timedelta

from why_moved.common.envelope import dart_viewer_url, envelope, source
from why_moved.context import AppContext
from why_moved.engine.disclosure_templates import match_template
from why_moved.engine.glossary import attach_terms

_SIGNIFICANT_FLOW = 1_000_000_000  # 순매수 10억원 이상이면 수급 요인으로 언급


async def why_moved(ctx: AppContext, query: str, date: str | None = None) -> dict:
    corp = await ctx.resolver.resolve(query)
    price = await ctx.market.get_price_move(corp.stock_code, date)
    day = price["date"]

    factors: list[dict] = []
    sources = [source("네이버 금융 시세 (KRX 데이터)", f"https://finance.naver.com/item/main.naver?code={corp.stock_code}", day)]

    # 1) 공시 요인: D-3 ~ 당일
    bgn = (datetime.strptime(day, "%Y%m%d") - timedelta(days=3)).strftime("%Y%m%d")
    disclosures = await ctx.dart.search_disclosures(corp_code=corp.corp_code, bgn_de=bgn, end_de=day)
    important = sorted(
        (d for d in disclosures if match_template(d.get("report_nm", "")).importance >= 3),
        key=lambda d: match_template(d["report_nm"]).importance,
        reverse=True,
    )
    for d in important[:2]:
        template = match_template(d["report_nm"])
        url = dart_viewer_url(d["rcept_no"])
        factors.append({
            "type": "disclosure",
            "summary": f"[{d['rcept_dt']}] {d['report_nm']} — {template.what_happened} {template.so_what}",
            "source_url": url,
        })
        sources.append(source(d["report_nm"], url, d["rcept_dt"]))

    # 2) 수급 요인 (기관·외국인 순매매, 추정대금)
    flow = None
    try:
        flow = await ctx.market.get_investor_flow(corp.stock_code, day)
        dominant = max(("외국인", "기관"), key=lambda k: abs(flow[k]))
        if abs(flow[dominant]) >= _SIGNIFICANT_FLOW:
            direction = "순매수" if flow[dominant] > 0 else "순매도"
            amount = abs(flow[dominant]) / 100_000_000
            factors.append({
                "type": "flow",
                "summary": f"{dominant}이 약 {amount:,.0f}억원(추정) {direction}했어요.",
                "source_url": f"https://finance.naver.com/item/frgn.naver?code={corp.stock_code}",
            })
    except Exception:
        pass  # 수급 조회 실패는 원인 후보 하나가 빠질 뿐, 응답은 계속한다

    # 3) 시장 요인: 지수가 같은 방향으로 1% 이상
    market = await ctx.market.get_market_of(corp.stock_code)
    index_change = await ctx.market.get_index_change(market, day)
    if abs(index_change) >= 1.0 and index_change * price["change_pct"] > 0:
        updown = "올랐" if index_change > 0 else "내렸"
        factors.append({
            "type": "market",
            "summary": f"{market} 지수 자체가 {index_change:+.1f}% {updown}어요. 시장 전체 흐름의 영향일 수 있어요.",
            "source_url": "https://finance.naver.com/sise/",
        })

    explanation = _build_explanation(corp.name, price, factors)
    payload = {
        "stock": {"name": corp.name, "code": corp.stock_code, "market": market},
        "price_move": price,
        "explanation": explanation,
        "factors": factors,
        "investor_flow": (
            {"date": flow["date"], "외국인": flow["외국인"], "기관": flow["기관"],
             "note": "순매매 주식수 × 종가 추정대금이에요. 개인 수급은 제공되지 않아요."}
            if flow else None
        ),
        "terms": attach_terms(explanation + " ".join(f["summary"] for f in factors)),
        "data_note": f"{day} 종가 기준 데이터예요 (실시간 아님).",
    }
    return envelope(payload, sources)


def _build_explanation(name: str, price: dict, factors: list[dict]) -> str:
    """3줄 요약. 환각 금지 — 요인이 없으면 없다고 말한다 (설계 §2.1)."""
    change = price["change_pct"]
    direction = "올랐어요" if change > 0 else ("내렸어요" if change < 0 else "보합이에요")
    first = f"{name}은(는) {price['date'][:4]}-{price['date'][4:6]}-{price['date'][6:]} 기준 {abs(change):.1f}% {direction}."

    if not factors:
        volume_note = ""
        if price.get("volume_ratio") and price["volume_ratio"] >= 3:
            volume_note = f" 다만 거래량이 평소의 {price['volume_ratio']:.0f}배로 뛰어 소문·테마성 움직임일 가능성은 있어요."
        return (
            f"{first} 공시·수급·시장 어디에서도 뚜렷한 공개 요인을 찾지 못했어요."
            f"{volume_note} 공개된 정보가 없는 움직임은 더 조심스럽게 보는 것이 좋아요."
        )

    reasons = " ".join(f"{i + 1}) {f['summary']}" for i, f in enumerate(factors[:3]))
    return f"{first} 확인된 공개 요인: {reasons}"
