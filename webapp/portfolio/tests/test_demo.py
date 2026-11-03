"""ログインなしのデモのテスト。"""

from datetime import date

from django.http import QueryDict
from django.test import TestCase

from portfolio import demo


class DemoCalculationTests(TestCase):
    def test_並行期間は重複せずに数える(self):
        params = QueryDict(
            "p1_start=2022-01&p1_end=2022-12&p1_skills=python"
            "&p2_start=2022-07&p2_end=2023-06&p2_skills=python"
            "&p3_start=2024-01&p3_end=2024-01"
        )
        result = demo.build_result(params, date(2025, 1, 1))
        self.assertEqual(result.errors, ())
        (row,) = result.rows
        self.assertEqual(
            (row.name, row.start_year, row.duration), ("Python", 2022, "1年6ヶ月")
        )

    def test_不正な入力は保持しエラーを返し算出しない(self):
        result = demo.build_result(
            QueryDict("p1_start=2024-05&p1_end=2024-01&p1_skills=aws"),
            date(2025, 1, 1),
        )
        self.assertEqual(len(result.errors), 3)
        self.assertEqual(result.rows, ())
        first = result.projects[0]
        self.assertEqual(
            (first.start, first.end, first.skills), ("2024-05", "2024-01", ("aws",))
        )

    def test_星の凡例は算出ロジックの基準と一致する(self):
        self.assertEqual(
            demo.STAR_LEGEND,
            (
                (1, "6ヶ月未満"),
                (2, "6ヶ月以上"),
                (3, "1年以上"),
                (4, "3年以上"),
                (5, "5年以上"),
            ),
        )


class DemoViewTests(TestCase):
    def test_ログインなしで表示できる(self):
        response = self.client.get("/demo/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("算出結果", html)
        self.assertIn("Python", html)

    def test_入力エラー時は入力を保持し結果を表示しない(self):
        response = self.client.get(
            "/demo/?p1_start=2024-05&p1_end=2024-01&p1_skills=aws"
        )
        html = response.content.decode()
        self.assertIn("終了年月は開始年月以降にしてください。", html)
        self.assertIn('value="2024-05"', html)
        self.assertNotIn("demo-table", html)

    def test_結果に星の基準と出力例への導線を表示する(self):
        html = self.client.get("/demo/").content.decode()
        self.assertIn("★3: 1年以上", html)
        self.assertIn('href="/#sample"', html)

    def test_保存せずHEADも許可する(self):
        self.assertEqual(self.client.head("/demo/").status_code, 200)
        self.assertEqual(self.client.post("/demo/").status_code, 405)

    def test_サービス紹介からリンクする(self):
        self.assertIn('href="/demo/"', self.client.get("/").content.decode())


class FaviconTests(TestCase):
    def test_faviconはSVGへ転送し各ページで読み込む(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("img/favicon.svg"))
        self.assertIn("favicon.svg", self.client.get("/").content.decode())
