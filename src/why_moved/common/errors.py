"""도메인 에러. tool 레이어에서 사용자 친화 메시지로 변환된다."""


class WhyMovedError(Exception):
    """서비스 공통 베이스 에러."""


class StockNotFoundError(WhyMovedError):
    def __init__(self, query: str):
        super().__init__(
            f"'{query}' 종목을 찾지 못했어요. 정확한 종목명 또는 6자리 종목코드로 다시 시도해 주세요."
        )


class DisclosureNotFoundError(WhyMovedError):
    def __init__(self, hint: str):
        super().__init__(f"해당 공시를 찾지 못했어요. ({hint})")


class UpstreamError(WhyMovedError):
    def __init__(self, upstream: str, detail: str = ""):
        super().__init__(
            f"{upstream} 데이터를 일시적으로 가져오지 못했어요. 잠시 후 다시 시도해 주세요."
            + (f" ({detail})" if detail else "")
        )
