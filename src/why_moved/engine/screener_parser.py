"""자연어 스크리너 조건 파서 (설계 §2.7).

지원 필드: 배당수익률(div), PER, PBR, 주가(close), 시장(market).
파싱 불가능한 조건은 unsupported로 정직하게 반환한다 (환각 금지).
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    field: str    # div | per | pbr | close | market
    op: str       # >= | <= | ==
    value: float | str


_FIELD_ALIASES = {
    "div": ("배당수익률", "배당률", "배당"),
    "per": ("per", "PER", "퍼", "주가수익비율"),
    "pbr": ("pbr", "PBR", "주가순자산비율"),
    "close": ("주가", "가격", "현재가"),
}

_ABOVE = ("이상", "넘는", "초과", "높은", "위")
_BELOW = ("이하", "미만", "낮은", "아래", "안되는")

_NUMBER_PATTERN = re.compile(
    r"(?P<keyword>[A-Za-z가-힣]+)\s*(?P<value>\d+(?:\.\d+)?)\s*(?:%|퍼센트|배|원)?\s*(?P<direction>[가-힣]+)?"
)


def parse_conditions(text: str) -> tuple[list[Condition], list[str]]:
    """(파싱된 조건, 해석 못한 조각) 을 반환한다."""
    conditions: list[Condition] = []
    consumed_spans: list[tuple[int, int]] = []

    if "코스피" in text or "KOSPI" in text.upper():
        conditions.append(Condition("market", "==", "KOSPI"))
    if "코스닥" in text or "KOSDAQ" in text.upper():
        conditions.append(Condition("market", "==", "KOSDAQ"))

    for m in _NUMBER_PATTERN.finditer(text):
        field = _resolve_field(m.group("keyword"))
        if field is None:
            continue
        direction = m.group("direction") or ""
        op = _resolve_op(direction, field)
        conditions.append(Condition(field, op, float(m.group("value"))))
        consumed_spans.append(m.span())

    unsupported = _leftover_fragments(text, consumed_spans)
    return conditions, unsupported


def _resolve_field(keyword: str) -> str | None:
    kw = keyword.strip()
    return next(
        (field for field, aliases in _FIELD_ALIASES.items()
         if any(a.lower() in kw.lower() or kw.lower() in a.lower() for a in aliases)),
        None,
    )


def _resolve_op(direction: str, field: str) -> str:
    if any(w in direction for w in _ABOVE):
        return ">="
    if any(w in direction for w in _BELOW):
        return "<="
    # 방향 미지정 기본값: 배당은 '이상', 밸류에이션·가격은 '이하'가 통상적 의도
    return ">=" if field == "div" else "<="


def _leftover_fragments(text: str, consumed: list[tuple[int, int]]) -> list[str]:
    """숫자 조건인데 필드를 못 알아들은 조각을 수집한다."""
    unsupported = []
    for m in _NUMBER_PATTERN.finditer(text):
        if m.span() in consumed:
            continue
        if _resolve_field(m.group("keyword")) is None:
            fragment = m.group(0).strip()
            # 시장명 등 이미 처리된 키워드는 제외
            if not any(k in fragment for k in ("코스피", "코스닥")):
                unsupported.append(fragment)
    return unsupported


def apply_conditions(rows: list[dict], conditions: list[Condition], limit: int = 20) -> list[dict]:
    """스냅샷 rows에 조건을 적용한다. 값 0(미산출 지표)은 비교 대상에서 제외."""
    result = []
    for row in rows:
        if all(_matches(row, c) for c in conditions):
            result.append(row)
        if len(result) >= limit * 5:  # 정렬 여유분
            break
    result.sort(key=lambda r: r.get("div", 0), reverse=True)
    return result[:limit]


def _matches(row: dict, c: Condition) -> bool:
    if c.field == "market":
        return row.get("market") == c.value
    value = row.get(c.field)
    if value is None or value == 0:  # KRX가 산출하지 않은 지표(적자기업 PER 등)
        return False
    if c.op == ">=":
        return value >= float(c.value)
    if c.op == "<=":
        return value <= float(c.value)
    return value == c.value
