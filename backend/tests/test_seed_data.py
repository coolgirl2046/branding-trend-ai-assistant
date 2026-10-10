import unittest
from unittest.mock import MagicMock, patch

from backend.scripts import seed_data
from backend.scripts.seed_data import (
    FIRESTORE_BATCH_SIZE,
    KEYWORDS,
    MEMO,
    REFERENCE_STATISTICS,
    STATISTICS_ABS_TOLERANCE,
    convert_workbook_to_records,
    make_document_id,
    run_seed,
    write_seed_records,
)


class SeedDataConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.validation = convert_workbook_to_records()

    def test_record_count_shape_types_and_keyword_counts(self):
        self.assertEqual(len(self.records), 558)
        self.assertEqual(
            self.validation["keyword_counts"],
            {keyword: 186 for keyword in KEYWORDS},
        )
        for record in self.records:
            self.assertEqual(
                set(record), {"date", "keyword", "value", "memo"}
            )
            self.assertIn(record["keyword"], KEYWORDS)
            self.assertIs(type(record["value"]), float)
            self.assertEqual(record["memo"], MEMO)

    def test_dates_and_data_quality_validation(self):
        self.assertEqual(self.validation["sheet_name"], "개요")
        self.assertEqual(self.validation["source_range"], "A1:F193")
        self.assertEqual(self.validation["week_count"], 186)
        self.assertEqual(self.validation["start_date"], "2023-01-02")
        self.assertEqual(self.validation["end_date"], "2026-07-20")
        self.assertTrue(self.validation["date_columns_identical"])
        self.assertTrue(self.validation["dates_ascending"])
        self.assertTrue(self.validation["all_intervals_seven_days"])
        self.assertEqual(self.validation["duplicate_date_keyword_count"], 0)
        self.assertEqual(self.validation["missing_value_count"], 0)
        self.assertEqual(self.validation["conversion_failure_count"], 0)
        self.assertTrue(self.validation["all_values_float"])
        self.assertTrue(self.validation["all_values_finite"])

    def test_statistics_match_verified_reference_values(self):
        for keyword in KEYWORDS:
            observed = self.validation["statistics"][keyword]
            expected = REFERENCE_STATISTICS[keyword]
            for statistic in ("average", "minimum", "maximum"):
                self.assertAlmostEqual(
                    observed[statistic],
                    expected[statistic],
                    delta=STATISTICS_ABS_TOLERANCE,
                )
                self.assertTrue(
                    self.validation["reference_matches"][keyword][statistic]
                )

    def test_document_id_uses_expected_keyword_slugs(self):
        self.assertEqual(
            make_document_id("2023-01-02", "퍼스널브랜딩"),
            "2023-01-02_personal-branding",
        )
        self.assertEqual(
            make_document_id("2023-01-02", "이미지메이킹"),
            "2023-01-02_image-making",
        )
        self.assertEqual(
            make_document_id("2023-01-02", "스피치"),
            "2023-01-02_speech",
        )

    def test_same_input_produces_same_document_id(self):
        first = make_document_id("2026-07-20", "스피치")
        second = make_document_id("2026-07-20", "스피치")
        self.assertEqual(first, second)

    def test_keyword_slugs_are_distinct(self):
        document_ids = {
            make_document_id("2023-01-02", keyword) for keyword in KEYWORDS
        }
        self.assertEqual(len(document_ids), len(KEYWORDS))

    def test_dry_run_never_calls_write_or_post_write_verification(self):
        with (
            patch.object(seed_data, "write_seed_records") as mocked_write,
            patch.object(seed_data, "verify_firestore_seed") as mocked_verify,
        ):
            result = run_seed(self.records)

        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["write_count"], 0)
        mocked_write.assert_not_called()
        mocked_verify.assert_not_called()

    def test_write_mode_orchestrates_mock_write_and_verification(self):
        client = MagicMock()
        write_result = {
            "write_count": 558,
            "batch_count": 2,
            "batch_sizes": [400, 158],
            "validation": self.validation,
        }
        post_write_result = {
            **self.validation,
            "firestore_document_count": 558,
            "document_id_mismatches": 0,
        }
        with (
            patch.object(
                seed_data, "write_seed_records", return_value=write_result
            ) as mocked_write,
            patch.object(
                seed_data,
                "verify_firestore_seed",
                return_value=post_write_result,
            ) as mocked_verify,
        ):
            result = run_seed(self.records, write=True, client=client)

        mocked_write.assert_called_once_with(self.records, client)
        mocked_verify.assert_called_once_with(client)
        self.assertEqual(result["mode"], "write")
        self.assertEqual(result["write_count"], 558)
        self.assertEqual(result["post_write_validation"], post_write_result)

    def test_558_records_are_split_into_safe_batches(self):
        client = MagicMock()
        batches = [MagicMock(), MagicMock()]
        client.batch.side_effect = batches

        result = write_seed_records(
            self.records, client, batch_size=FIRESTORE_BATCH_SIZE
        )

        self.assertEqual(result["batch_sizes"], [400, 158])
        self.assertEqual(result["batch_count"], 2)
        self.assertEqual(result["write_count"], 558)
        self.assertEqual(batches[0].set.call_count, 400)
        self.assertEqual(batches[1].set.call_count, 158)
        batches[0].commit.assert_called_once_with()
        batches[1].commit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
