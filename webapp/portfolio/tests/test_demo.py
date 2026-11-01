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

    def test_不正な入力は既定値に戻しエラーを返す(self):
        result = demo.build_result(
            QueryDict("p1_start=2024-05&p1_end=2024-01"), date(2025, 1, 1)
        )
        self.assertEqual(len(result.errors), 3)
        self.assertEqual(result.projects[0], demo.DEFAULT_PROJECTS[0])


class DemoViewTests(TestCase):
    def test_ログインなしで表示できる(self):
        response = self.client.get("/demo/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("算出結果", html)
        self.assertIn("Python", html)

    def test_保存せずHEADも許可する(self):
        self.assertEqual(self.client.head("/demo/").status_code, 200)
        self.assertEqual(self.client.post("/demo/").status_code, 405)

    def test_サービス紹介からリンクする(self):
        self.assertIn('href="/demo/"', self.client.get("/").content.decode())
