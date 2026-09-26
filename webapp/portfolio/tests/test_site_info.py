from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from portfolio.models import SiteInfo
from portfolio.services import calculate_age, format_copyright
from portfolio.tests.test_manage import LoggedInTestCase

VALID_PAYLOAD = {
    "name": "山田 太郎",
    "typing_titles": ["肩書きA", "肩書きB"],
    "catchphrase": "こんにちは",
    "intro": "自己紹介\n2 行目",
    "birth_date": "1990-05-10",
    "job": "エンジニア",
    "education": "大学卒",
    "location": "東京都",
    "hobby": "読書",
    "github_url": "https://github.com/example",
    "contact_message": "お問い合わせください",
    "contact_form_url": "https://example.com/form",
    "copyright_start_year": 2024,
}


class CalculateAgeTests(SimpleTestCase):
    def test_誕生日前は1歳引く(self):
        self.assertEqual(calculate_age(date(1990, 5, 10), date(2026, 5, 9)), 35)

    def test_誕生日当日に加算される(self):
        self.assertEqual(calculate_age(date(1990, 5, 10), date(2026, 5, 10)), 36)


class FormatCopyrightTests(SimpleTestCase):
    def test_開始年と現在の年が同じなら1つの年のみ(self):
        self.assertEqual(format_copyright(2026, date(2026, 1, 1)), "2026")

    def test_開始年が過去なら範囲表記(self):
        self.assertEqual(format_copyright(2024, date(2026, 1, 1)), "2024-2026")


class PublicSiteApiTests(TestCase):
    def test_未登録なら404(self):
        self.assertEqual(self.client.get(reverse("api-site")).status_code, 404)

    def test_年齢を返し生年月日を含まない(self):
        payload = dict(VALID_PAYLOAD, birth_date=date(1990, 5, 10))
        SiteInfo.objects.create(**payload)
        response = self.client.get(reverse("api-site"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("age", body)
        self.assertNotIn("birth_date", body)
        self.assertNotIn("1990", response.content.decode())
        self.assertEqual(body["typing_titles"], ["肩書きA", "肩書きB"])


class ManageSiteApiTests(LoggedInTestCase):
    def test_未ログインでは401(self):
        self.client.logout()
        self.assertEqual(self.call("get", "manage-api-site").status_code, 401)

    def test_未登録なら空のフォーム値を返す(self):
        body = self.call("get", "manage-api-site").json()
        self.assertEqual(body["typing_titles"], [])
        self.assertEqual(body["name"], "")

    def test_保存して取得できる_2回目は更新になる(self):
        self.assertEqual(
            self.call("put", "manage-api-site", VALID_PAYLOAD).status_code, 200
        )
        changed = dict(VALID_PAYLOAD, job="変更後")
        body = self.call("put", "manage-api-site", changed).json()
        self.assertEqual(body["job"], "変更後")
        self.assertEqual(body["birth_date"], "1990-05-10")
        self.assertEqual(SiteInfo.objects.count(), 1)

    def test_肩書きが空ならエラー(self):
        response = self.call(
            "put", "manage-api-site", dict(VALID_PAYLOAD, typing_titles=[])
        )
        self.assertEqual(response.status_code, 400)

    def test_不正な生年月日はエラー(self):
        response = self.call(
            "put", "manage-api-site", dict(VALID_PAYLOAD, birth_date="abc")
        )
        self.assertEqual(response.status_code, 400)


class ImportSiteInfoTests(TestCase):
    def test_空のときのみ投入され再実行では変更しない(self):
        call_command("import_portfolio_data", stdout=StringIO())
        info = SiteInfo.objects.get()
        info.job = "変更済み"
        info.save()
        call_command("import_portfolio_data", stdout=StringIO())
        self.assertEqual(SiteInfo.objects.get().job, "変更済み")
