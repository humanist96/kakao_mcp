"""envelope·캐시·파서 등 공통 레이어 테스트."""

import time

from why_moved.adapters.market_data import _num, _parse_frgn_table
from why_moved.cache.store import TTLCache
from why_moved.common.envelope import (
    contains_forbidden_phrase,
    dart_viewer_url,
    envelope,
    source,
)


class TestEnvelope:
    def test_envelope_attaches_contract_fields(self):
        result = envelope({"a": 1}, [source("t", "http://u")])
        assert result["a"] == 1
        assert result["sources"][0]["url"] == "http://u"
        assert "투자 자문이 아닙니다" in result["disclaimer"]

    def test_envelope_does_not_mutate_payload(self):
        payload = {"a": 1}
        envelope(payload, [])
        assert "disclaimer" not in payload

    def test_forbidden_phrase_detection(self):
        assert contains_forbidden_phrase("지금 매수하세요") == "매수하세요"
        assert contains_forbidden_phrase("공시 사실의 요약입니다") is None

    def test_dart_viewer_url(self):
        assert "rcpNo=123" in dart_viewer_url("123")


class TestTTLCache:
    def test_set_get_roundtrip(self, tmp_path):
        cache = TTLCache(str(tmp_path / "c.db"))
        cache.set("k", {"v": 1, "한글": "값"}, ttl_seconds=60)
        assert cache.get("k") == {"v": 1, "한글": "값"}

    def test_expiry(self, tmp_path, monkeypatch):
        cache = TTLCache(str(tmp_path / "c.db"))
        cache.set("k", "v", ttl_seconds=10)
        future = time.time() + 11
        monkeypatch.setattr(time, "time", lambda: future)
        assert cache.get("k") is None

    def test_missing_key(self, tmp_path):
        cache = TTLCache(str(tmp_path / "c.db"))
        assert cache.get("nope") is None


class TestMarketDataParsers:
    def test_num_parses_korean_formats(self):
        assert _num("25.02배") == 25.02
        assert _num("0.54%") == 0.54
        assert _num("309,500") == 309500
        assert _num("N/A") is None
        assert _num(None) is None

    def test_parse_frgn_table(self):
        html = """
        <tr><td>2026.07.03</td><td>309,500</td><td>상승</td><td>+8.22%</td>
        <td>31,498,600</td><td>+4,369,649</td><td>-1,365,575</td><td>x</td><td>46%</td></tr>
        <tr><td>헤더아님</td></tr>
        """
        rows = _parse_frgn_table(html)
        assert len(rows) == 1
        assert rows[0]["inst_shares"] == 4369649
        assert rows[0]["frgn_shares"] == -1365575
