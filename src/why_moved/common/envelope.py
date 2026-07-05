"""모든 tool 응답에 강제되는 공통 envelope.

설계 원칙(§1): 출처 필수, 고지 필수, 추천 표현 금지.
"""

from typing import Any

DISCLAIMER = (
    "본 정보는 DART·KRX 등 공개 데이터에 기반한 사실의 요약이며, "
    "특정 종목의 매수·매도를 권유하는 투자 자문이 아닙니다. "
    "투자의 최종 판단과 책임은 투자자 본인에게 있습니다."
)

# 해석 템플릿·요약문에 절대 포함되면 안 되는 권유성 표현 (안전망 검사용)
FORBIDDEN_PHRASES = (
    "매수하세요",
    "매도하세요",
    "사세요",
    "파세요",
    "추천합니다",
    "목표주가",
    "수익 보장",
    "확실합니다",
)


def source(title: str, url: str, date: str = "") -> dict[str, str]:
    return {"title": title, "url": url, "date": date}


def dart_viewer_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def envelope(payload: dict[str, Any], sources: list[dict[str, str]]) -> dict[str, Any]:
    """payload에 sources/disclaimer를 부착한 새 응답 객체를 만든다."""
    return {
        **payload,
        "sources": sources,
        "disclaimer": DISCLAIMER,
    }


def contains_forbidden_phrase(text: str) -> str | None:
    """권유성 표현이 있으면 해당 표현을 반환, 없으면 None."""
    return next((p for p in FORBIDDEN_PHRASES if p in text), None)
