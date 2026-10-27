"""OGP・canonical・robots.txt・sitemap.xml・アクセス解析・公開ポートフォリオの名称のテスト。"""

from datetime import date

from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from portfolio.models import SiteInfo
from portfolio.tests.helpers import create_user

TOKEN = "0123456789abcdef"
BEACON = "static.cloudflareinsights.com/beacon.min.js"


def _site_info(owner, name="山田 太郎", catchphrase="インフラを支える"):
    return SiteInfo.objects.create(
        owner=owner,
        name=name,
        typing_titles=["a"],
        catchphrase=catchphrase,
        intro="i",
        birth_date=date(1990, 1, 1),
        job="j",
        education="e",
        location="l",
        hobby="h",
        github_url="https://github.com/x",
        contact_message="m",
        contact_form_url="https://example.com",
        copyright_start_year=2024,
    )


class ServicePageShareMetaTests(TestCase):
    def test_サービス紹介にOGPとcanonicalを出力する(self):
        html = self.client.get(reverse("index") + "?ref=x").content.decode()
        self.assertIn('<meta property="og:title" content="SkillSheet" />', html)
        self.assertIn('content="summary_large_image"', html)
        self.assertIn(
            '<meta property="og:image" content="http://testserver/static/img/ogp.png" />',
            html,
        )
        # canonical はクエリ文字列を含めない
        self.assertIn('<link rel="canonical" href="http://testserver/" />', html)

    def test_規約のOGPは規約の名称を用いる(self):
        html = self.client.get(reverse("terms")).content.decode()
        self.assertIn('content="利用規約 | SkillSheet"', html)
        html = self.client.get(reverse("privacy")).content.decode()
        self.assertIn('content="プライバシーポリシー | SkillSheet"', html)

    def test_共有用の画像が存在する(self):
        self.assertIsNotNone(finders.find("img/ogp.png"))


class PortfolioShareMetaTests(TestCase):
    def test_タイトルとロゴにユーザーの氏名を用いる(self):
        user = create_user("taro", public=True)
        _site_info(user)
        html = self.client.get(reverse("portfolio", args=["taro"])).content.decode()
        self.assertIn("<title>山田 太郎 | Portfolio</title>", html)
        self.assertIn('content="山田 太郎 | Portfolio"', html)
        self.assertIn('content="インフラを支える"', html)
        self.assertIn('aria-label="トップへ戻る">山田 太郎</a>', html)
        self.assertNotIn("Seiya Nakagawa", html)

    def test_サイト情報が未登録ならユーザー名とサービスの説明を用いる(self):
        create_user("hanako", public=True)
        html = self.client.get(reverse("portfolio", args=["hanako"])).content.decode()
        self.assertIn("<title>hanako | Portfolio</title>", html)
        self.assertIn("経験年数の自動算出", html)

    def test_氏名はエスケープして出力する(self):
        user = create_user("jiro", public=True)
        _site_info(user, name="<script>x</script>", catchphrase='"q"')
        html = self.client.get(reverse("portfolio", args=["jiro"])).content.decode()
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", html)

    def test_フッターに本サービスで作成したことを示す(self):
        create_user("saburo", public=True)
        html = self.client.get(reverse("portfolio", args=["saburo"])).content.decode()
        self.assertIn("SkillSheet で作成</a>", html)


class AnalyticsTests(TestCase):
    def test_トークン未設定なら計測用スクリプトを出力しない(self):
        create_user("taro", public=True)
        for url in (reverse("index"), reverse("portfolio", args=["taro"])):
            self.assertNotIn(BEACON, self.client.get(url).content.decode())

    @override_settings(CLOUDFLARE_ANALYTICS_TOKEN=TOKEN)
    def test_公開ページにのみ計測用スクリプトを出力する(self):
        create_user("taro", public=True)
        for url in (
            reverse("index"),
            reverse("terms"),
            reverse("privacy"),
            reverse("portfolio", args=["taro"]),
        ):
            html = self.client.get(url).content.decode()
            self.assertIn(BEACON, html, url)
            self.assertIn(TOKEN, html, url)
        for url in (reverse("login"), reverse("manage")):
            self.client.force_login(create_user())
            html = self.client.get(url).content.decode()
            self.assertNotIn(BEACON, html, url)


class CrawlerFilesTests(TestCase):
    def test_robots_txtはログインが必要な画面を拒否しサイトマップを示す(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        body = response.content.decode()
        for path in ("/manage/", "/admin/", "/accounts/", "/login/", "/media/"):
            self.assertIn(f"Disallow: {path}", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_sitemap_xmlはサービスの公開ページのみを列挙する(self):
        create_user("taro", public=True)
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        body = response.content.decode()
        for path in ("/", "/terms/", "/privacy/"):
            self.assertIn(f"<loc>http://testserver{path}</loc>", body)
        self.assertNotIn("/u/", body)
