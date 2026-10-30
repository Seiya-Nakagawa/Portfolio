"""解説記事の一覧・記事ページのテスト。"""

from django.test import TestCase
from django.urls import reverse

from portfolio.articles import ARTICLES


class ArticleTests(TestCase):
    def test_記事は2本以上公開している(self):
        self.assertGreaterEqual(len(ARTICLES), 2)

    def test_一覧は全記事へのリンクを出力する(self):
        html = self.client.get(reverse("article-list")).content.decode()
        for article in ARTICLES:
            self.assertIn(reverse("article-detail", args=[article.slug]), html)

    def test_記事はタイトル_説明_OGP_canonicalを出力する(self):
        for article in ARTICLES:
            with self.subTest(slug=article.slug):
                url = reverse("article-detail", args=[article.slug])
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn(f"<title>{article.title} | SkillSheet</title>", html)
                self.assertIn(
                    f'<meta name="description" content="{article.description}" />',
                    html,
                )
                self.assertIn(f'content="{article.title} | SkillSheet"', html)
                self.assertIn(
                    f'<link rel="canonical" href="http://testserver{url}" />', html
                )
                # 本文のテンプレート変数が展開されている
                self.assertNotIn("{{", html)
                self.assertNotIn("{%", html)

    def test_存在しない記事は404(self):
        self.assertEqual(self.client.get("/articles/unknown/").status_code, 404)

    def test_記事はHEADに200を返す(self):
        url = reverse("article-detail", args=[ARTICLES[0].slug])
        self.assertEqual(self.client.head(url).status_code, 200)
