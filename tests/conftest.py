"""공용 픽스처 — 어댑터를 모킹한 AppContext."""

from unittest.mock import AsyncMock

import pytest

from why_moved.adapters.corp_codes import Corp
from why_moved.context import AppContext

SAMSUNG = Corp(corp_code="00126380", stock_code="005930", name="삼성전자")


@pytest.fixture
def mock_ctx():
    """모든 어댑터가 AsyncMock인 컨텍스트. 테스트에서 반환값을 지정해 사용한다."""
    dart = AsyncMock()
    market = AsyncMock()
    kind = AsyncMock()
    resolver = AsyncMock()
    resolver.resolve.return_value = SAMSUNG
    resolver.name_map.return_value = {"005930": "삼성전자"}

    # 합리적 기본값 (개별 테스트에서 덮어씀)
    market.get_price_move.return_value = {
        "date": "20260703", "close": 309500, "change_pct": 8.22,
        "volume": 31_498_600, "volume_ratio": 1.0,
    }
    market.get_investor_flow.return_value = {
        "date": "20260703", "기관": 1_352_400_000_000, "외국인": -422_600_000_000,
        "unit_note": "",
    }
    market.get_investor_flow_range.return_value = {
        "start": "20260604", "end": "20260703", "기관": 1_000_000_000_000,
        "외국인": -500_000_000_000, "연기금": 0,
    }
    market.get_index_change.return_value = 0.3
    market.get_market_of.return_value = "KOSPI"
    market.get_fundamental.return_value = {"per": 25.0, "pbr": 4.3, "div": 0.54}
    market.get_fundamental_snapshot.return_value = []
    market.latest_trading_day.return_value = "20260703"

    dart.search_disclosures.return_value = []
    dart.get_financials.return_value = []
    dart.get_executive_holdings.return_value = []
    dart.get_major_holdings.return_value = []
    kind.is_managed.return_value = False
    kind.is_unfaithful.return_value = False

    return AppContext(dart=dart, market=market, kind=kind, resolver=resolver)
