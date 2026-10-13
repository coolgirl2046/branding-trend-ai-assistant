"""stdio MCP server exposing the shared read-only Firestore trend tool."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from backend.app.database import get_firestore_client
from backend.app.services.trend_tools import (
    TrendToolInputError,
    get_weekly_interest_data,
)


server = MCPServer(
    "branding-trend-ai-assistant",
    instructions=(
        "Read-only access to weekly Naver DataLab relative search-interest "
        "data. This index is not absolute search volume."
    ),
    version="1.0.0",
)


@server.tool()
def query_weekly_interest(
    keyword: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Read one supported keyword's weekly relative-interest values by date range."""

    try:
        return get_weekly_interest_data(
            get_firestore_client(),
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
        )
    except TrendToolInputError as exc:
        raise ToolError(str(exc)) from None
    except Exception:
        raise ToolError("요청한 Firestore 데이터를 조회하지 못했습니다.") from None


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
