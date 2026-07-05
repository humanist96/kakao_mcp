"""템플릿·용어사전·건강점수·재무추출·스크리너 파서 유닛테스트."""

from why_moved.engine.disclosure_templates import DEFAULT_TEMPLATE, match_template
from why_moved.engine.financial_extract import extract_financials
from why_moved.engine.glossary import attach_terms
from why_moved.engine.health_score import (
    FinancialSnapshot,
    axis_scores,
    narrative,
    overall_grade,
    run_checks,
)
from why_moved.engine.screener_parser import apply_conditions, parse_conditions


class TestTemplates:
    def test_rights_offering_matched(self):
        t = match_template("주요사항보고서(유상증자결정)")
        assert t.type_name == "유상증자"
        assert t.importance == 5

    def test_cb_matched(self):
        assert match_template("전환사채권발행결정").type_name == "전환사채 발행"

    def test_unknown_falls_back_to_default(self):
        assert match_template("기타경영사항") is DEFAULT_TEMPLATE

    def test_no_recommendation_phrases_in_templates(self):
        from why_moved.common.envelope import contains_forbidden_phrase
        from why_moved.engine.disclosure_templates import TEMPLATES

        for t in TEMPLATES:
            combined = t.what_happened + t.so_what + t.why_care
            assert contains_forbidden_phrase(combined) is None, t.type_name


class TestGlossary:
    def test_attach_terms_finds_terms(self):
        terms = attach_terms("이번 유상증자로 오버행 우려가 있어요.")
        found = {t["term"] for t in terms}
        assert "유상증자" in found
        assert "오버행" in found

    def test_attach_terms_limit(self):
        text = " ".join(["유상증자 무상증자 전환사채 리픽싱 오버행 보호예수 자사주"])
        assert len(attach_terms(text, limit=3)) == 3


class TestHealthScore:
    def _snapshot(self):
        return FinancialSnapshot(
            revenue=1000, operating_income=100, net_income=80,
            equity=500, liabilities=400,
            prev_revenue=900, prev_operating_income=90,
            per=10.0, pbr=1.0, div_yield=3.0,
        )

    def test_checks_pass_for_healthy_company(self):
        checks = run_checks(self._snapshot())
        assert all(c.passed for c in checks)
        assert len(checks) == 10

    def test_axis_scores_in_range(self):
        scores = axis_scores(self._snapshot())
        assert all(v is not None and 0 <= v <= 100 for v in scores.values())

    def test_grade_for_missing_data(self):
        assert overall_grade({"value": None, "growth": None}) == "N/A"

    def test_narrative_mentions_pass_count(self):
        checks = run_checks(self._snapshot())
        text = narrative(checks, "A")
        assert "10개 중 10개" in text

    def test_empty_snapshot_produces_no_checks(self):
        assert run_checks(FinancialSnapshot()) == []


class TestFinancialExtract:
    def test_extracts_core_accounts(self):
        rows = [
            {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "1,000", "frmtrm_amount": "900"},
            {"sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "100", "frmtrm_amount": "90"},
            {"sj_div": "IS", "account_nm": "당기순이익", "thstrm_amount": "80"},
            {"sj_div": "BS", "account_nm": "자본총계", "thstrm_amount": "500"},
            {"sj_div": "BS", "account_nm": "부채총계", "thstrm_amount": "400"},
            {"sj_div": "BS", "account_nm": "자본금", "thstrm_amount": "50"},
        ]
        f = extract_financials(rows)
        assert f["revenue"] == 1000
        assert f["prev_revenue"] == 900
        assert f["equity"] == 500
        assert f["capital"] == 50

    def test_bs_income_confusion_avoided(self):
        # 자본총계는 BS에서만, 매출액은 IS/CIS에서만 수집한다
        rows = [
            {"sj_div": "IS", "account_nm": "자본총계", "thstrm_amount": "999"},
            {"sj_div": "BS", "account_nm": "매출액", "thstrm_amount": "888"},
        ]
        f = extract_financials(rows)
        assert f["equity"] is None
        assert f["revenue"] is None


class TestScreenerParser:
    def test_parse_dividend_and_market(self):
        conditions, unsupported = parse_conditions("배당수익률 4% 이상 코스피")
        fields = {(c.field, c.op) for c in conditions}
        assert ("div", ">=") in fields
        assert ("market", "==") in fields
        assert unsupported == []

    def test_parse_pbr_below(self):
        conditions, _ = parse_conditions("PBR 1 이하")
        assert conditions[0].field == "pbr"
        assert conditions[0].op == "<="
        assert conditions[0].value == 1.0

    def test_unknown_condition_reported(self):
        conditions, unsupported = parse_conditions("ROE 15% 이상")
        assert conditions == []
        assert unsupported  # 정직하게 미지원 보고

    def test_apply_conditions_filters(self):
        rows = [
            {"code": "A", "market": "KOSPI", "per": 5, "pbr": 0.8, "div": 5.0, "close": 100},
            {"code": "B", "market": "KOSPI", "per": 50, "pbr": 4.0, "div": 0.5, "close": 200},
            {"code": "C", "market": "KOSDAQ", "per": 8, "pbr": 0.9, "div": 4.5, "close": 300},
        ]
        conditions, _ = parse_conditions("배당수익률 4% 이상 PBR 1 이하 코스피")
        matched = apply_conditions(rows, conditions)
        assert [r["code"] for r in matched] == ["A"]

    def test_zero_metric_excluded(self):
        # PER 0(적자 등 미산출)은 'PER 10 이하' 조건에 걸리면 안 된다
        rows = [{"code": "A", "market": "KOSPI", "per": 0, "pbr": 1, "div": 1, "close": 100}]
        conditions, _ = parse_conditions("PER 10 이하")
        assert apply_conditions(rows, conditions) == []
