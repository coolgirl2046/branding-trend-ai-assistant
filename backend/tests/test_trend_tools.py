"""Input validation and read-only tests for shared trend tools."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from backend.app.services.summary import METRIC_NOTE
from backend.app.services.trend_tools import (
    FUNCTION_TOOL_SCHEMA,
    TOOL_NAME,
    TrendToolInputError,
    execute_trend_tool,
    get_weekly_interest_data,
)


class Snapshot:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


class Collection:
    def __init__(self, snapshots: list[Snapshot]):
        self.snapshots = snapshots

    def stream(self) -> list[Snapshot]:
        return list(self.snapshots)


class ReadOnlyFakeFirestore:
    def __init__(self):
        self.snapshots = [
            Snapshot(
                {
                    "date": "2026-06-08",
                    "keyword": "스피치",
                    "value": 51,
                    "memo": "DO_NOT_LOG_FIREBASE_PRIVATE_KEY",
                }
            ),
            Snapshot({"date": "2026-06-01", "keyword": "스피치", "value": 50}),
            Snapshot({"date": "2026-06-01", "keyword": "퍼스널브랜딩", "value": 10}),
            Snapshot({"date": "2026-06-15", "keyword": "스피치", "value": 52}),
        ]
        self.collection_names: list[str] = []

    def collection(self, name: str) -> Collection:
        self.collection_names.append(name)
        return Collection(self.snapshots)


class TrendToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ReadOnlyFakeFirestore()

    def test_schema_limits_keywords_and_requires_all_arguments(self) -> None:
        function = FUNCTION_TOOL_SCHEMA["function"]
        self.assertEqual(function["name"], TOOL_NAME)
        self.assertEqual(
            function["parameters"]["properties"]["keyword"]["enum"],
            ["퍼스널브랜딩", "이미지메이킹", "스피치"],
        )
        self.assertEqual(
            function["parameters"]["required"],
            ["keyword", "start_date", "end_date"],
        )
        self.assertFalse(function["parameters"]["additionalProperties"])

    def test_returns_sorted_inclusive_range_and_sanitized_records(self) -> None:
        result = get_weekly_interest_data(
            self.client,
            keyword="스피치",
            start_date="2026-06-01",
            end_date="2026-06-08",
        )

        self.assertEqual(result["metric_note"], METRIC_NOTE)
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual([item["date"] for item in result["records"]], [
            "2026-06-01",
            "2026-06-08",
        ])
        self.assertEqual(result["records"][0]["value"], 50.0)
        self.assertNotIn("memo", result["records"][1])
        self.assertEqual(self.client.collection_names, ["data"])

    def test_success_logs_only_tool_name_keyword_range_and_count(self) -> None:
        with self.assertLogs(
            "backend.app.services.trend_tools", level="INFO"
        ) as captured:
            result = execute_trend_tool(
                self.client,
                TOOL_NAME,
                {
                    "keyword": "스피치",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-08",
                },
            )

        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(
            captured.output,
            [
                "INFO:backend.app.services.trend_tools:"
                "trend_tool_success tool_name=get_weekly_interest_data "
                "keyword=스피치 start_date=2026-06-01 end_date=2026-06-08 "
                "returned_count=2"
            ],
        )
        self.assertNotIn("DO_NOT_LOG_FIREBASE_PRIVATE_KEY", captured.output[0])
        self.assertNotIn("conversation_id", captured.output[0])
        self.assertNotIn("api_key", captured.output[0].lower())

    def test_rejects_unsupported_keyword_without_firestore_read(self) -> None:
        with self.assertRaisesRegex(TrendToolInputError, "지원하지 않는 키워드"):
            execute_trend_tool(
                self.client,
                TOOL_NAME,
                {
                    "keyword": "다른 키워드",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-08",
                },
            )
        self.assertEqual(self.client.collection_names, [])

    def test_rejects_invalid_and_reversed_dates(self) -> None:
        with self.assertRaisesRegex(TrendToolInputError, "유효한"):
            get_weekly_interest_data(
                self.client,
                keyword="스피치",
                start_date="2026-02-30",
                end_date="2026-03-01",
            )
        with self.assertRaisesRegex(TrendToolInputError, "늦을 수 없습니다"):
            get_weekly_interest_data(
                self.client,
                keyword="스피치",
                start_date="2026-06-08",
                end_date="2026-06-01",
            )
        self.assertEqual(self.client.collection_names, [])

    def test_rejects_long_date_range_and_extra_tool_arguments(self) -> None:
        with self.assertRaisesRegex(TrendToolInputError, "최대 5년"):
            get_weekly_interest_data(
                self.client,
                keyword="스피치",
                start_date="2020-01-01",
                end_date="2026-01-01",
            )
        with self.assertRaisesRegex(TrendToolInputError, "누락되거나"):
            execute_trend_tool(
                self.client,
                TOOL_NAME,
                {
                    "keyword": "스피치",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-08",
                    "collection": "conversations",
                },
            )
        self.assertEqual(self.client.collection_names, [])


class MCPTrendToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_is_registered_and_calls_shared_read_function(self) -> None:
        from backend.app import mcp_server

        client = ReadOnlyFakeFirestore()
        registered = await mcp_server.server.list_tools()
        self.assertIn("query_weekly_interest", [tool.name for tool in registered])

        with patch(
            "backend.app.mcp_server.get_firestore_client", return_value=client
        ):
            result = await mcp_server.server.call_tool(
                "query_weekly_interest",
                {
                    "keyword": "이미지메이킹",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-08",
                },
            )

        self.assertFalse(result.is_error)
        self.assertEqual(client.collection_names, ["data"])
        structured = result.structured_content
        self.assertEqual(structured["keyword"], "이미지메이킹")
        self.assertEqual(structured["observation_count"], 0)
        self.assertEqual(structured["metric_note"], METRIC_NOTE)

    async def test_stdio_transport_with_official_sdk_client(self) -> None:
        from mcp import Client, StdioServerParameters

        project_root = Path(__file__).resolve().parents[2]
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "backend.app.mcp_server"],
            cwd=project_root,
            env={"PYTHONPATH": str(project_root)},
        )

        async with Client(parameters) as client:
            listed = await client.list_tools()
            self.assertIn("query_weekly_interest", [tool.name for tool in listed.tools])
            invalid_call = await client.call_tool(
                "query_weekly_interest",
                {
                    "keyword": "unsupported",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-08",
                },
            )

        self.assertTrue(invalid_call.is_error)


if __name__ == "__main__":
    unittest.main()
