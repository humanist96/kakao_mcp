"""insider_signal — 스마트머니 피드 (설계 §2.5).

DART 임원·주요주주 소유보고(≈美 Form 4) + 5% 대량보유(≈13F) + KRX 수급.
법적으로 검증된 '진짜 돈'의 움직임만 다룬다.
"""

from datetime import datetime, timedelta

from why_moved.common.envelope import dart_viewer_url, envelope, source
from why_moved.context import AppContext


async def insider_signal(ctx: AppContext, query: str, days: int = 30) -> dict:
    corp = await ctx.resolver.resolve(query)
    cut = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    events: list[dict] = []
    sources = [source("DART 지분공시", "https://dart.fss.or.kr")]

    for row in await ctx.dart.get_executive_holdings(corp.corp_code):
        event = _executive_event(row, cut)
        if event:
            events.append(event)

    for row in await ctx.dart.get_major_holdings(corp.corp_code):
        event = _major_holder_event(row, cut)
        if event:
            events.append(event)

    events.sort(key=lambda e: e["date"], reverse=True)

    flow = None
    try:
        flow = await ctx.market.get_investor_flow_range(corp.stock_code, days)
        sources.append(source(
            "기관·외국인 매매동향 (네이버 금융)",
            f"https://finance.naver.com/item/frgn.naver?code={corp.stock_code}",
            flow["end"],
        ))
    except Exception:
        pass

    payload = {
        "stock": {"name": corp.name, "code": corp.stock_code},
        "period_days": days,
        "events": events[:20],
        "institutional_flow": flow,
        "summary": _summary(corp.name, days, events, flow),
    }
    return envelope(payload, sources)


def _executive_event(row: dict, cut: str) -> dict | None:
    date = row.get("rcept_dt", "")
    if date < cut:
        return None
    change = _num(row.get("sp_stock_lmp_irds_cnt"))
    if change == 0:
        return None
    return {
        "date": date,
        "who": row.get("repror", "임원·주요주주"),
        "role": row.get("isu_exctv_ofcps") or row.get("isu_main_shrholdr", ""),
        "action": "매수" if change > 0 else "매도",
        "shares": abs(int(change)),
        "kind": "임원·주요주주 소유보고",
        "source_url": dart_viewer_url(row.get("rcept_no", "")),
    }


def _major_holder_event(row: dict, cut: str) -> dict | None:
    date = row.get("rcept_dt", "")
    if date < cut:
        return None
    ratio = _num(row.get("stkrt"))
    prev_ratio = _num(row.get("stkrt_irds"))
    return {
        "date": date,
        "who": row.get("repror", "대량보유자"),
        "role": "5% 이상 주주",
        "action": "지분 변동",
        "ratio": ratio,
        "ratio_change": prev_ratio,
        "kind": "5% 대량보유 보고",
        "source_url": dart_viewer_url(row.get("rcept_no", "")),
    }


def _num(raw) -> float:
    try:
        return float(str(raw or "0").replace(",", ""))
    except ValueError:
        return 0.0


def _summary(name: str, days: int, events: list[dict], flow: dict | None) -> str:
    parts = []
    buys = [e for e in events if e.get("action") == "매수"]
    sells = [e for e in events if e.get("action") == "매도"]
    if buys or sells:
        parts.append(
            f"최근 {days}일간 {name} 내부자 공시: 매수 {len(buys)}건, 매도 {len(sells)}건이에요."
        )
    else:
        parts.append(f"최근 {days}일간 {name}의 내부자 매매 공시는 없었어요.")
    if flow:
        dominant = max(("외국인", "기관"), key=lambda k: abs(flow.get(k, 0)))
        amount = flow.get(dominant, 0) / 100_000_000
        if abs(amount) >= 1:
            direction = "순매수" if amount > 0 else "순매도"
            parts.append(f"같은 기간 {dominant}은 약 {abs(amount):,.0f}억원(추정) {direction}했어요.")
    parts.append("내부자 매수는 통상 자신감 신호로 해석되곤 하지만, 그 자체가 주가 상승을 보장하지는 않아요.")
    return " ".join(parts)
