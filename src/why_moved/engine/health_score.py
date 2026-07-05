"""5축 건강점수 + A~F 학점 (설계 §2.4).

공시 실적(DART)과 시장 밸류에이션(KRX)만으로 계산한다 — 미래 예측 없음.
점수는 지표별 절대 구간이 아니라 임계 테이블 기반이지만, 학점 산출 시
'시장 전체 대비 상대적 위치'라는 표현을 유지하도록 내러티브를 만든다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FinancialSnapshot:
    """최근 사업연도 재무 요약 (DART) + 밸류에이션 (KRX)."""

    revenue: float | None = None            # 매출액
    operating_income: float | None = None   # 영업이익
    net_income: float | None = None         # 당기순이익
    equity: float | None = None             # 자본총계
    liabilities: float | None = None        # 부채총계
    prev_revenue: float | None = None
    prev_operating_income: float | None = None
    per: float | None = None
    pbr: float | None = None
    div_yield: float | None = None          # 배당수익률(%)


@dataclass(frozen=True)
class HealthCheck:
    name: str
    passed: bool
    easy_explanation: str


def _pct(part: float, whole: float) -> float:
    return part / whole * 100 if whole else 0.0


def run_checks(f: FinancialSnapshot) -> list[HealthCheck]:
    """개별 체크 목록. 데이터 없는 체크는 제외한다 (정직한 분모)."""
    checks: list[HealthCheck] = []

    if f.operating_income is not None:
        checks.append(HealthCheck(
            "영업이익 흑자", f.operating_income > 0,
            "본업에서 이익을 내고 있는지 봐요."))
    if f.net_income is not None:
        checks.append(HealthCheck(
            "당기순이익 흑자", f.net_income > 0,
            "최종적으로 남는 이익이 있는지 봐요."))
    if f.revenue is not None and f.prev_revenue:
        checks.append(HealthCheck(
            "매출 성장", f.revenue > f.prev_revenue,
            "작년보다 매출이 늘었는지 봐요."))
    if f.operating_income is not None and f.prev_operating_income is not None:
        checks.append(HealthCheck(
            "영업이익 성장", f.operating_income > f.prev_operating_income,
            "작년보다 본업 이익이 늘었는지 봐요."))
    if f.revenue and f.operating_income is not None:
        checks.append(HealthCheck(
            "영업이익률 5% 이상", _pct(f.operating_income, f.revenue) >= 5,
            "매출 대비 이익이 충분한지 봐요."))
    if f.equity is not None and f.net_income is not None and f.equity > 0:
        checks.append(HealthCheck(
            "ROE 5% 이상", _pct(f.net_income, f.equity) >= 5,
            "자기자본으로 얼마나 이익을 냈는지 봐요."))
    if f.equity and f.liabilities is not None:
        checks.append(HealthCheck(
            "부채비율 200% 미만", _pct(f.liabilities, f.equity) < 200,
            "빚이 자기자본 대비 과하지 않은지 봐요."))
    if f.pbr is not None and f.pbr > 0:
        checks.append(HealthCheck(
            "PBR 3배 미만", f.pbr < 3,
            "장부가치 대비 주가가 과하게 높지 않은지 봐요."))
    if f.per is not None and f.per > 0:
        checks.append(HealthCheck(
            "PER 30배 미만", f.per < 30,
            "이익 대비 주가가 과하게 높지 않은지 봐요."))
    if f.div_yield is not None:
        checks.append(HealthCheck(
            "배당 지급", f.div_yield > 0,
            "주주에게 이익을 나눠주는지 봐요."))
    return checks


def axis_scores(f: FinancialSnapshot) -> dict[str, int | None]:
    """5축 점수 (0~100). 데이터 부족 축은 None."""

    def clamp(v: float) -> int:
        return max(0, min(100, round(v)))

    value = None
    if f.per and f.per > 0 and f.pbr and f.pbr > 0:
        # PER 30배=0점, 5배 이하=100점 / PBR 5배=0점, 0.5 이하=100점 평균
        per_score = clamp((30 - f.per) / 25 * 100)
        pbr_score = clamp((5 - f.pbr) / 4.5 * 100)
        value = (per_score + pbr_score) // 2

    growth = None
    if f.revenue and f.prev_revenue:
        growth_rate = _pct(f.revenue - f.prev_revenue, f.prev_revenue)
        growth = clamp(50 + growth_rate * 2.5)  # +20% 성장 = 100점, -20% = 0점

    profitability = None
    if f.revenue and f.operating_income is not None:
        margin = _pct(f.operating_income, f.revenue)
        profitability = clamp(margin * 5)  # 영업이익률 20% = 100점

    stability = None
    if f.equity and f.liabilities is not None:
        debt_ratio = _pct(f.liabilities, f.equity)
        stability = clamp(100 - debt_ratio / 3)  # 부채비율 300% = 0점

    dividend = None
    if f.div_yield is not None:
        dividend = clamp(f.div_yield * 20)  # 배당수익률 5% = 100점

    return {
        "value": value,
        "growth": growth,
        "profitability": profitability,
        "stability": stability,
        "dividend": dividend,
    }


def overall_grade(scores: dict[str, int | None]) -> str:
    """유효 축 평균 → A+~F 학점."""
    valid = [v for v in scores.values() if v is not None]
    if not valid:
        return "N/A"
    avg = sum(valid) / len(valid)
    bands = [(90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C+"), (40, "C"), (30, "D"), (0, "F")]
    return next(grade for threshold, grade in bands if avg >= threshold)


def narrative(checks: list[HealthCheck], grade: str) -> str:
    """쉬운 문장 요약 (설계: '체크 N개 중 M개 통과')."""
    if not checks:
        return "재무 데이터가 부족해 진단을 완료하지 못했어요."
    passed = sum(1 for c in checks if c.passed)
    lines = [f"기본 체크 {len(checks)}개 중 {passed}개를 통과했어요. 종합 학점은 {grade}예요."]
    failed = [c for c in checks if not c.passed][:3]
    if failed:
        names = ", ".join(c.name for c in failed)
        lines.append(f"아쉬운 항목: {names}.")
    return " ".join(lines)
