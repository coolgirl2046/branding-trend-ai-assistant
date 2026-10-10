import unittest
from datetime import date, timedelta

from backend.app.services.summary import (
    INSUFFICIENT_DATA,
    METRIC_NOTE,
    calculate_summary,
)


def make_weekly_records(keyword, values, start=date(2024, 1, 1)):
    return [
        {
            "date": (start + timedelta(weeks=index)).isoformat(),
            "keyword": keyword,
            "value": value,
            "memo": "테스트 데이터" if index == 0 else None,
        }
        for index, value in enumerate(values)
    ]


class CalculateSummaryTests(unittest.TestCase):
    def test_complete_summary_trends_ranking_and_shuffled_input(self):
        records = []
        records.extend(make_weekly_records("퍼스널브랜딩", [1, 1, 1, 1, 3, 3, 3, 3]))
        records.extend(make_weekly_records("이미지메이킹", [8, 8, 8, 8, 4, 4, 4, 4]))
        records.extend(
            make_weekly_records("스피치", [10, 10, 10, 10, 10.2, 10.2, 10.2, 10.2])
        )
        records = records[::2][::-1] + records[1::2][::-1]

        result = calculate_summary(records)

        self.assertEqual(result["start_date"], "2024-01-01")
        self.assertEqual(result["end_date"], "2024-02-19")
        self.assertEqual(result["total_count"], 24)
        self.assertIn("상대 검색 관심도 지수", result["metric_note"])

        personal = result["keywords"]["퍼스널브랜딩"]
        self.assertEqual(personal["count"], 8)
        self.assertEqual(personal["average"], 2.0)
        self.assertEqual(personal["minimum"], 1.0)
        self.assertEqual(personal["maximum"], 3.0)
        self.assertEqual(personal["latest_date"], "2024-02-19")
        self.assertEqual(personal["latest_value"], 3.0)
        self.assertEqual(personal["recent_4week_average"], 3.0)
        self.assertEqual(personal["previous_4week_average"], 1.0)
        self.assertEqual(personal["difference"], 2.0)
        self.assertEqual(personal["trend"], "상승")

        image = result["keywords"]["이미지메이킹"]
        self.assertEqual(image["previous_4week_average"], 8.0)
        self.assertEqual(image["recent_4week_average"], 4.0)
        self.assertEqual(image["difference"], -4.0)
        self.assertEqual(image["trend"], "하락")

        speech = result["keywords"]["스피치"]
        self.assertEqual(speech["average"], 10.1)
        self.assertEqual(speech["recent_4week_average"], 10.2)
        self.assertEqual(speech["previous_4week_average"], 10.0)
        self.assertEqual(speech["difference"], 0.2)
        self.assertEqual(speech["trend"], "유지")

        self.assertEqual(
            [item["keyword"] for item in result["ranking"]],
            ["스피치", "이미지메이킹", "퍼스널브랜딩"],
        )
        self.assertEqual(
            [item["rank"] for item in result["ranking"]],
            [1, 2, 3],
        )

    def test_difference_at_threshold_is_stable(self):
        records = make_weekly_records(
            "퍼스널브랜딩", [5, 5, 5, 5, 5.5, 5.5, 5.5, 5.5]
        )

        summary = calculate_summary(records)["keywords"]["퍼스널브랜딩"]

        self.assertEqual(summary["difference"], 0.5)
        self.assertEqual(summary["trend"], "유지")

    def test_four_to_seven_records_have_only_recent_average(self):
        records = make_weekly_records("퍼스널브랜딩", [1, 2, 3, 4, 5, 6, 7])

        result = calculate_summary(records)
        summary = result["keywords"]["퍼스널브랜딩"]

        self.assertEqual(summary["recent_4week_average"], 5.5)
        self.assertIsNone(summary["previous_4week_average"])
        self.assertIsNone(summary["difference"])
        self.assertEqual(summary["trend"], INSUFFICIENT_DATA)
        self.assertEqual(result["ranking"][0]["keyword"], "퍼스널브랜딩")

    def test_fewer_than_four_records_have_no_four_week_metrics(self):
        records = make_weekly_records("이미지메이킹", [2, 4, 6])

        result = calculate_summary(records)
        summary = result["keywords"]["이미지메이킹"]

        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["average"], 4.0)
        self.assertEqual(summary["latest_value"], 6.0)
        self.assertIsNone(summary["recent_4week_average"])
        self.assertIsNone(summary["previous_4week_average"])
        self.assertIsNone(summary["difference"])
        self.assertEqual(summary["trend"], INSUFFICIENT_DATA)
        self.assertEqual(result["ranking"], [])

    def test_empty_input_returns_explicit_empty_summary(self):
        result = calculate_summary([])

        self.assertIsNone(result["start_date"])
        self.assertIsNone(result["end_date"])
        self.assertEqual(result["total_count"], 0)
        self.assertEqual(result["ranking"], [])
        for keyword in ("퍼스널브랜딩", "이미지메이킹", "스피치"):
            self.assertEqual(result["keywords"][keyword]["count"], 0)
            self.assertEqual(result["keywords"][keyword]["trend"], INSUFFICIENT_DATA)

    def test_invalid_input_is_rejected(self):
        invalid_records = [
            {"date": "2024-13-01", "keyword": "스피치", "value": 10},
            {"date": "2024-01-01", "keyword": "알 수 없음", "value": 10},
            {"date": "2024-01-01", "keyword": "스피치", "value": 101},
        ]

        for record in invalid_records:
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    calculate_summary([record])

    def test_custom_threshold_must_be_non_negative(self):
        with self.assertRaises(ValueError):
            calculate_summary([], stability_threshold=-0.1)

        result = calculate_summary([], stability_threshold=1.0)
        self.assertEqual(result["trend_rule"]["stability_threshold"], 1.0)
        self.assertEqual(result["metric_note"], METRIC_NOTE)
