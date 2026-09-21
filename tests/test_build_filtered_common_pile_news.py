"""Tests for the filtered Common Pile News source builder."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_filtered_common_pile_news.py"
SPEC = importlib.util.spec_from_file_location("filtered_source_builder", SCRIPT)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class FilteredSourceBuilderTests(unittest.TestCase):
    def test_a_passage_keeps_only_one_consecutive_safe_run(self) -> None:
        text = "\n".join(
            [
                "Title",
                "Author",
                "January 2, 2023",
                "Alpha company increased revenue in its latest quarter. " * 8,
                'A spokesperson said "this copied statement is external."',
                "Beta company reduced costs and increased production capacity. " * 8,
            ]
        )

        passage, removals = BUILDER.longest_safe_passage(text)

        self.assertIsNotNone(passage)
        self.assertNotIn("external", passage)
        self.assertTrue(
            any(item["reason"] == "direct-or-block-quotation" for item in removals)
        )

    def test_a_url_date_has_priority(self) -> None:
        self.assertEqual(
            date(2023, 4, 5),
            BUILDER.parse_published_date(
                "https://example.test/2023/04/05/story/", "January 1, 2001"
            ),
        )

    def test_a_single_curly_quotation_is_removed(self) -> None:
        self.assertEqual(
            "direct-or-block-quotation",
            BUILDER.sentence_reason("The source called it ‘a copied statement’."),
        )

    def test_the_fixed_periods_are_disjoint(self) -> None:
        periods = {
            "training": {"start": "2000-01-01", "end": "2021-12-31"},
            "development": {"start": "2022-01-01", "end": "2022-12-31"},
            "blind": {"start": "2023-01-01", "end": "2024-12-31"},
        }

        self.assertEqual("training", BUILDER.split_for(date(2021, 12, 31), periods))
        self.assertEqual("development", BUILDER.split_for(date(2022, 1, 1), periods))
        self.assertEqual("blind", BUILDER.split_for(date(2024, 12, 31), periods))
        self.assertIsNone(BUILDER.split_for(date(2025, 1, 1), periods))


if __name__ == "__main__":
    unittest.main()
