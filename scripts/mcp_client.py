"""왜움직여? MCP 서버 테스트 클라이언트.

MCP Streamable HTTP 프로토콜로 서버에 접속해 tool을 호출한다.
PlayMCP 등록 전 로컬/원격 서버 검증용.

사용법:
    uv run python scripts/mcp_client.py                          # tool 목록
    uv run python scripts/mcp_client.py demo                     # 데모 시나리오 실행
    uv run python scripts/mcp_client.py call why_moved '{"query": "삼성전자"}'
    MCP_URL=https://<도메인>/mcp uv run python scripts/mcp_client.py demo
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DEFAULT_URL = "http://127.0.0.1:8000/mcp"

DEMO_CALLS: list[tuple[str, dict]] = [
    ("why_moved", {"query": "삼성전자"}),
    ("risk_check", {"query": "삼성전자"}),
    ("explain_disclosure", {"company": "삼성전자"}),
    ("stock_health", {"query": "카카오"}),
    ("insider_signal", {"query": "삼성전자", "days": 30}),
    ("daily_digest", {}),
    ("screen_stocks", {"condition": "배당수익률 4% 이상 PBR 1 이하 코스피"}),
]


def _print_result(name: str, result) -> None:
    print(f"\n{'=' * 60}\n🔧 {name}\n{'=' * 60}")
    if result.isError:
        print("❌ isError=True")
    for content in result.content:
        if content.type != "text":
            print(f"[{content.type}]")
            continue
        try:
            data = json.loads(content.text)
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        except json.JSONDecodeError:
            print(content.text[:2000])


async def run(url: str, mode: str, tool: str | None, args: dict) -> None:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"✅ 연결: {url}")
            print(f"   서버: {init.serverInfo.name} (protocol {init.protocolVersion})")

            tools = await session.list_tools()
            print(f"   tools: {[t.name for t in tools.tools]}")

            if mode == "list":
                for t in tools.tools:
                    print(f"\n- {t.name}: {t.description[:80]}")
                return

            calls = [(tool, args)] if mode == "call" else DEMO_CALLS
            for name, call_args in calls:
                try:
                    result = await session.call_tool(name, call_args)
                    _print_result(f"{name} {json.dumps(call_args, ensure_ascii=False)}", result)
                except Exception as exc:
                    print(f"\n❌ {name} 호출 실패: {exc}")


def main() -> None:
    url = os.environ.get("MCP_URL", DEFAULT_URL)
    argv = sys.argv[1:]
    if not argv:
        mode, tool, args = "list", None, {}
    elif argv[0] == "demo":
        mode, tool, args = "demo", None, {}
    elif argv[0] == "call" and len(argv) >= 2:
        mode = "call"
        tool = argv[1]
        args = json.loads(argv[2]) if len(argv) >= 3 else {}
    else:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(url, mode, tool, args))


if __name__ == "__main__":
    main()
