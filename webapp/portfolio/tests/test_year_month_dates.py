import importlib
from datetime import date

from django.test import SimpleTestCase

from portfolio.services import format_year_month

migration = importlib.import_module("portfolio.migrations.0010_year_month_dates")


class ParseYearMonthTests(SimpleTestCase):
    def test_取得日の文言を月初の日付に変換する(self):
        cases = {
            "Jul 2024": date(2024, 7, 1),
            "September 2020": date(2020, 9, 1),
            "2023-04": date(2023, 4, 1),
            "2022年12月": date(2022, 12, 1),
        }
        for label, expected in cases.items():
            with self.subTest(label):
                self.assertEqual(migration.parse_year_month(label), expected)

    def test_読み取れない文言はエラー(self):
        with self.assertRaises(ValueError):
            migration.parse_year_month("不明")


class FormatYearMonthTests(SimpleTestCase):
    def test_YYYY年MM月に整形する(self):
        self.assertEqual(format_year_month(date(2024, 7, 1)), "2024年07月")
