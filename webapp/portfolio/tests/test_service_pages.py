"""サービス紹介・利用規約・プライバシーポリシー・フッターのリンク・初回利用の案内のテスト。"""

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse

from portfolio.tests.helpers import create_operator, create_user

FORM_URL = "https://forms.example.com/contact"


class ServiceIndexTests(TestCase):
    def test_特長_利用の流れ_出力例_ログインボタンを表示する(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for text in (
            "経験年数の自動算出",
            "職務経歴書 PDF の自動生成",
            "案件・スキル・資格の一元管理",
            "利用の流れ",
            "職務経歴書の出力例",
            "架空のデータ",
        ):
            self.assertIn(text, html)
        self.assertNotIn("ポートフォリオ", html)
        self.assertIn("/static/img/skillsheet-sample.png", html)
        self.assertIn(reverse("login"), html)

    def test_ログイン中は登録画面への導線を表示する(self):
        self.client.force_login(create_user("taro"))
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn(reverse("manage"), html)
        self.assertNotIn("Google / GitHub で始める", html)

    def test_出力例の画像が存在する(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("img/skillsheet-sample.png"))


class LegalPagesTests(TestCase):
    def test_規約とプライバシーポリシーを版つきで表示する(self):
        terms = self.client.get(reverse("terms")).content.decode()
        self.assertIn("利用規約", terms)
        self.assertIn(settings.TERMS_VERSION, terms)
        self.assertIn("退会", terms)
        privacy = self.client.get(reverse("privacy")).content.decode()
        self.assertIn("プライバシーポリシー", privacy)
        self.assertIn(settings.PRIVACY_VERSION, privacy)

    def test_プライバシーポリシーに必要な事項を含む(self):
        html = self.client.get(reverse("privacy")).content.decode()
        for text in (
            "取得する情報",
            "利用目的",
            "保存期間",
            "第三者",
            "約 12 か月",
            "職務経歴書データ",
            "削除",
        ):
            self.assertIn(text, html)

    def test_現行の版の本文テンプレートが存在する(self):
        # 版を改定したときに、本文のテンプレートの追加を忘れないための確認。
        get_template(f"legal/terms/{settings.TERMS_VERSION}.html")
        get_template(f"legal/privacy/{settings.PRIVACY_VERSION}.html")

    def test_本文に運営者の個人情報を含めない(self):
        for name in ("terms", "privacy"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertNotIn("@", html)

    def test_版を改定すると本文のテンプレートが切り替わる(self):
        with (
            override_settings(TERMS_VERSION="2099-01-01"),
            self.assertRaises(TemplateDoesNotExist),
        ):
            self.client.get(reverse("terms"))


class FooterLinksTests(TestCase):
    def _pages(self):
        owner = create_operator("taro")
        return {
            "service": self.client.get(reverse("index")),
            "terms": self.client.get(reverse("terms")),
            "login": self.client.get(reverse("login")),
            "portfolio": self.client.get(reverse("portfolio", args=[owner.username])),
        }

    @override_settings(CONTACT_FORM_URL=FORM_URL)
    def test_問い合わせ_規約_プライバシーポリシーへのリンクを置く(self):
        for name, response in self._pages().items():
            html = response.content.decode()
            with self.subTest(name):
                self.assertIn(reverse("terms"), html)
                self.assertIn(reverse("privacy"), html)
                self.assertIn(FORM_URL, html)

    @override_settings(CONTACT_FORM_URL="")
    def test_問い合わせ先が未設定ならリンクを表示しない(self):
        # 公開ポートフォリオ自体の Contact の導線とは別に、サービスのフッターのリンクを確認する。
        for name, response in self._pages().items():
            if name == "portfolio":
                continue
            with self.subTest(name):
                self.assertNotIn("お問い合わせ</a>", response.content.decode())


class FirstUseGuideTests(TestCase):
    def test_登録画面に初回利用の案内を用意する(self):
        self.client.force_login(create_user("taro"))
        html = self.client.get(reverse("manage")).content.decode()
        self.assertIn('id="first-use-guide"', html)
        self.assertIn("はじめにやること", html)
