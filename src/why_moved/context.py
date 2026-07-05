"""애플리케이션 컨텍스트 — 어댑터·캐시를 한 곳에서 조립한다."""

from dataclasses import dataclass

from why_moved.adapters.corp_codes import CorpCodeResolver
from why_moved.adapters.dart import DartClient
from why_moved.adapters.kind import KindClient
from why_moved.adapters.market_data import MarketDataClient
from why_moved.cache.store import TTLCache
from why_moved.config import Settings


@dataclass(frozen=True)
class AppContext:
    dart: DartClient
    market: MarketDataClient
    kind: KindClient
    resolver: CorpCodeResolver


def build_context(settings: Settings) -> AppContext:
    cache = TTLCache(settings.cache_db_path)
    return AppContext(
        dart=DartClient(settings.dart_api_key, cache, settings.http_timeout_seconds),
        market=MarketDataClient(cache, settings.http_timeout_seconds),
        kind=KindClient(cache, settings.http_timeout_seconds),
        resolver=CorpCodeResolver(settings.dart_api_key, cache),
    )
