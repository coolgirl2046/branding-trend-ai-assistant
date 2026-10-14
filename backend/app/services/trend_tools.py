"""Read-only tool shared by chat Function Calling and the MCP server."""

from __future__ import annotations

import logging
import math
from datetime import date
from numbers import Real
from typing import Any

from backend.app.services.summary import ALLOWED_KEYWORDS, METRIC_NOTE
from backend.scripts.seed_data import FIRESTORE_COLLECTION


logger = logging.getLogger(__name__)
TOOL_NAME = "get_weekly_interest_data"
MAX_DATE_RANGE_DAYS = 5 * 366
TOOL_DESCRIPTION = (
    "Read weekly Naver DataLab relative search-interest index observations "
    "for one supported branding keyword and an inclusive date range. "
    "This is relative interest, not absolute search volume."
)

FUNCTION_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "enum": list(ALLOWED_KEYWORDS),
                    "description": "검색할 키워드",
                },
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "조회 시작일(YYYY-MM-DD, 포함)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "조회 종료일(YYYY-MM-DD, 포함)",
                },
            },
            "required": ["keyword", "start_date", "end_date"],
            "additionalProperties": False,
        },
    },
}


class TrendToolInputError(ValueError):
    """Raised when a tool request has invalid or unsupported arguments."""


def _parse_date(value: object, field_name: str) -> date:
    if not isinstance(value, str):
        raise TrendToolInputError(f"{field_name}는 YYYY-MM-DD 형식이어야 합니다.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise TrendToolInputError(
            f"{field_name}는 유효한 YYYY-MM-DD 날짜여야 합니다."
        ) from None
    if parsed.isoformat() != value:
        raise TrendToolInputError(f"{field_name}는 YYYY-MM-DD 형식이어야 합니다.")
    return parsed


def get_weekly_interest_data(
    client: Any,
    *,
    keyword: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Return sanitized weekly observations for a supported keyword/date range."""

    if keyword not in ALLOWED_KEYWORDS:
        raise TrendToolInputError("지원하지 않는 키워드입니다.")
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start > end:
        raise TrendToolInputError("start_date는 end_date보다 늦을 수 없습니다.")
    if (end - start).days > MAX_DATE_RANGE_DAYS:
        raise TrendToolInputError("조회 기간은 최대 5년으로 제한됩니다.")

    records: list[dict[str, Any]] = []
    for snapshot in client.collection(FIRESTORE_COLLECTION).stream():
        stored = snapshot.to_dict()
        if stored.get("keyword") != keyword:
            continue
        observed_date = _parse_date(stored.get("date"), "저장된 date")
        if start <= observed_date <= end:
            raw_value = stored.get("value")
            if (
                isinstance(raw_value, bool)
                or not isinstance(raw_value, Real)
                or not math.isfinite(float(raw_value))
                or not 0 <= float(raw_value) <= 100
            ):
                raise ValueError("Firestore에 유효하지 않은 관심도 값이 있습니다.")
            records.append(
                {
                    "date": observed_date.isoformat(),
                    "keyword": keyword,
                    "value": float(raw_value),
                }
            )

    records.sort(key=lambda record: record["date"])
    logger.info(
        "trend_tool_success tool_name=%s keyword=%s start_date=%s end_date=%s returned_count=%d",
        TOOL_NAME,
        keyword,
        start.isoformat(),
        end.isoformat(),
        len(records),
    )
    return {
        "metric_note": METRIC_NOTE,
        "keyword": keyword,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "observation_count": len(records),
        "records": records,
    }


def execute_trend_tool(
    client: Any,
    name: str,
    arguments: object,
) -> dict[str, Any]:
    """Dispatch only the allowlisted read-only trend tool."""

    if name != TOOL_NAME:
        raise TrendToolInputError("허용되지 않은 도구입니다.")
    if not isinstance(arguments, dict):
        raise TrendToolInputError("도구 인자는 JSON 객체여야 합니다.")
    expected = {"keyword", "start_date", "end_date"}
    if set(arguments) != expected:
        raise TrendToolInputError("도구 인자에 누락되거나 지원하지 않는 필드가 있습니다.")
    return get_weekly_interest_data(
        client,
        keyword=arguments["keyword"],
        start_date=arguments["start_date"],
        end_date=arguments["end_date"],
    )
