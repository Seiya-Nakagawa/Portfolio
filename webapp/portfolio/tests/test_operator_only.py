from django.test import TestCase
from django.urls import reverse

from portfolio.tests.helpers import create_operator, create_user

PASSWORD = "pw-for-test"


class PublicPortfolioIsOperatorOnlyTests(TestCase):
    """公開ポートフォリオは運営者のみ。一般ユーザーは公開設定が真でも 404 とする。"""

    def test_運営者の公開ポートフォリオは表示できる(self):
        create_operator("ops")
        self.assertEqual(self.client.get("/u/ops/").status_code, 200)
        self.assertEqual(self.client.get("/u/ops/api/works").status_code, 200)

    def test_一般ユーザーは公開設定が真でも404(self):
        create_user("taro", public=True)
        self.assertEqual(self.client.get("/u/taro/").status_code, 404)
        for name in ("works", "site", "certifications"):
            self.assertEqual(self.client.get(f"/u/taro/api/{name}").status_code, 404)

    def test_一般ユーザーの画像は他人に配信しない(self):
        owner = create_user("taro", public=True)
        response = self.client.get(f"/media/users/{owner.pk}/works/a.png")
        self.assertEqual(response.status_code, 404)

    def test_一般ユーザーのサイトマップ掲載なし(self):
        create_user("taro", public=True)
        self.assertNotIn("/u/taro/", self.client.get("/sitemap.xml").content.decode())


class ManageApiIsOperatorOnlyTests(TestCase):
    """実績・サイト情報・画像のアップロードは運営者のみ使える。"""

    def setUp(self):
        self.user = create_user("taro", password=PASSWORD)
        self.client.force_login(self.user)

    def test_一般ユーザーは実績とサイト情報のAPIを使えない(self):
        for name in ("manage-api-works", "manage-api-site"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("manage-api-works"), data="{}", content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                reverse("manage-api-site"), data="{}", content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("manage-api-upload-image")).status_code, 403
        )

    def test_管理画面に実績とサイト情報を表示しない(self):
        content = self.client.get(reverse("manage")).content.decode()
        self.assertNotIn('data-tab="works"', content)
        self.assertNotIn('data-tab="site"', content)
        self.assertIn('data-tab="certifications"', content)

    def test_運営者の管理画面には実績とサイト情報を表示する(self):
        self.client.force_login(create_operator("ops"))
        content = self.client.get(reverse("manage")).content.decode()
        self.assertIn('data-tab="works"', content)
        self.assertIn('data-tab="site"', content)
