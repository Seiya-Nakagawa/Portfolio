"""ユーザー別の公開ポートフォリオ・画像の配信・旧 URL のリダイレクト・画像の移行のテスト。"""

import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from portfolio.models import Certification, SiteInfo, Work
from portfolio.tests.helpers import create_operator, create_user

PUBLIC_API_NAMES = ("api-skills", "api-certifications", "api-works", "api-site")


def _site_info(owner):
    return SiteInfo.objects.create(
        owner=owner,
        name="氏名",
        typing_titles=["a"],
        catchphrase="c",
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


class PublicPortfolioVisibilityTests(TestCase):
    """非公開・存在しない・利用停止中のユーザーは、区別せず同一の 404 とする。"""

    def _responses(self, username):
        return [
            self.client.get(reverse("portfolio", args=[username])),
            *[
                self.client.get(reverse(name, args=[username]))
                for name in PUBLIC_API_NAMES
            ],
        ]

    def test_公開中のユーザーはページとAPIを表示できる(self):
        owner = create_user("taro", public=True)
        _site_info(owner)
        for response in self._responses("taro"):
            self.assertEqual(response.status_code, 200, response.request["PATH_INFO"])

    def test_ユーザー名の大文字小文字を区別しない(self):
        create_user("Taro", public=True)
        self.assertEqual(
            self.client.get(reverse("portfolio", args=["TARO"])).status_code, 200
        )

    def test_非公開_存在しない_利用停止中は同一の404になる(self):
        create_user("private-user", public=False)
        stopped = create_user("stopped-user", public=True)
        stopped.is_active = False
        stopped.save()
        bodies = set()
        for username in ("private-user", "nobody", "stopped-user"):
            for response in self._responses(username):
                self.assertEqual(response.status_code, 404, username)
                bodies.add(response.content)
        self.assertEqual(len(bodies), 1, "404 の内容がユーザーの状態で異なる")

    def test_プロフィールのないユーザーは表示しない(self):
        create_user("no-profile", agreed=False)
        self.assertEqual(
            self.client.get(reverse("portfolio", args=["no-profile"])).status_code, 404
        )

    def test_公開APIは対象ユーザーのデータのみを返す(self):
        a = create_user("user-a", public=True)
        b = create_user("user-b", public=True)
        Certification.objects.create(
            owner=a, name="資格A", acquired_on=date(2024, 1, 1), org="X"
        )
        Certification.objects.create(
            owner=b, name="資格B", acquired_on=date(2024, 1, 1), org="X"
        )
        body = self.client.get(reverse("api-certifications", args=["user-a"])).json()
        self.assertEqual([c["name"] for c in body], ["資格A"])

    def test_書き込み系のメソッドは許可しない(self):
        create_user("taro", public=True)
        for name in PUBLIC_API_NAMES:
            self.assertEqual(
                self.client.post(reverse(name, args=["taro"])).status_code, 405, name
            )

    def test_トップはサービス紹介を表示し運営者のポートフォリオを表示しない(self):
        create_operator()
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("data-api-skills", response.content.decode())


class MediaAccessTests(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.owner = create_user("owner", password="pw-for-test")
        self.other = create_user("other", password="pw-for-test")

    def _put(self, user, name="a.png"):
        relative = f"users/{user.pk}/works/{name}"
        path = Path(self._media.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG-data")
        return f"/media/{relative}"

    def _set_public(self, user, is_public):
        user.profile.is_public = is_public
        user.profile.save()

    def test_公開中のユーザーの画像は誰でも見られる(self):
        self._set_public(self.owner, True)
        self.assertEqual(self.client.get(self._put(self.owner)).status_code, 200)

    def test_非公開のユーザーの画像は他の閲覧者には404(self):
        url = self._put(self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_非公開でも本人は見られる(self):
        url = self._put(self.owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_利用停止中のユーザーの画像は404(self):
        self._set_public(self.owner, True)
        url = self._put(self.owner)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_存在しないユーザーの保存先や従来の保存先は404(self):
        (Path(self._media.name) / "works").mkdir()
        (Path(self._media.name) / "works" / "old.png").write_bytes(b"x")
        self.assertEqual(self.client.get("/media/works/old.png").status_code, 404)
        self.assertEqual(
            self.client.get("/media/users/99999/works/a.png").status_code, 404
        )

    def test_ディレクトリを遡るパスは配信しない(self):
        self._set_public(self.owner, True)
        self._put(self.owner)
        response = self.client.get(f"/media/users/{self.owner.pk}/../../secret.png")
        self.assertIn(response.status_code, (301, 400, 404))


class ThumbnailOwnershipTests(TestCase):
    def setUp(self):
        self.user = create_user("owner", password="pw-for-test")
        self.other = create_user("other")
        self.client.force_login(self.user)

    def _save(self, thumbnail):
        payload = {
            "title": "T",
            "desc_ja": "d",
            "achieved_on": "2025-01",
            "thumbnail": thumbnail,
        }
        return self.client.post(
            reverse("manage-api-works"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_自分の保存先の画像は指定できる(self):
        response = self._save(f"users/{self.user.pk}/works/a.png")
        self.assertEqual(response.status_code, 200)

    def test_他のユーザーの保存先の画像は指定できない(self):
        response = self._save(f"users/{self.other.pk}/works/a.png")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Work.objects.count(), 0)

    def test_外部URLや従来の画像は指定できる(self):
        self.assertEqual(self._save("https://example.com/a.png").status_code, 200)
        self.assertEqual(self._save("img/a.png").status_code, 200)


class LegacyUrlRedirectTests(TestCase):
    def setUp(self):
        override = override_settings(
            ALLOWED_HOSTS=["testserver", "legacy.example.com", "service.example.com"],
            LEGACY_HOSTS=["legacy.example.com"],
            SERVICE_HOST="service.example.com",
            LEGACY_REDIRECT_USERNAME="operator",
        )
        override.enable()
        self.addCleanup(override.disable)

    def _get(self, path):
        return self.client.get(path, HTTP_HOST="legacy.example.com")

    def test_公開ポートフォリオへ301で転送する(self):
        for path in (
            "/",
            "/portfolio/",
            "/portfolio",
            "/api/skills",
            "/portfolio/api/works",
        ):
            with self.subTest(path):
                response = self._get(path)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(
                    response["Location"], "https://service.example.com/u/operator/"
                )

    def test_管理画面はサービスホストの同じ画面へ転送する(self):
        for path, expected in {
            "/manage/": "/manage/",
            "/portfolio/manage/": "/manage/",
            "/portfolio/manage/api/skills": "/manage/api/skills",
        }.items():
            with self.subTest(path):
                response = self._get(path)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(
                    response["Location"], f"https://service.example.com{expected}"
                )

    def test_クエリは管理画面への転送で引き継ぐ(self):
        response = self._get("/manage/?next=/manage/")
        self.assertEqual(
            response["Location"], "https://service.example.com/manage/?next=/manage/"
        )

    def test_静的ファイルやAPIを含め_リダイレクト以外を応答しない(self):
        for path in (
            "/static/css/style.css",
            "/login/",
            "/media/x.png",
            "/u/operator/",
        ):
            with self.subTest(path):
                self.assertEqual(self._get(path).status_code, 301)

    def test_転送先のユーザー名が未設定ならサービスホストのトップへ転送する(self):
        with override_settings(LEGACY_REDIRECT_USERNAME=""):
            self.assertEqual(
                self._get("/portfolio/")["Location"], "https://service.example.com/"
            )

    def test_サービスホストは通常どおり応答する(self):
        response = self.client.get("/", HTTP_HOST="service.example.com")
        self.assertEqual(response.status_code, 200)

    def test_旧URLのホストを設定しなければ転送しない(self):
        with override_settings(LEGACY_HOSTS=[]):
            self.assertEqual(self._get("/").status_code, 200)


class MigrateMediaCommandTests(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.root = Path(self._media.name)
        self.owner = create_user("owner")

    def _legacy_work(self, name="a.png", write=True):
        if write:
            (self.root / "works").mkdir(exist_ok=True)
            (self.root / "works" / name).write_bytes(b"png")
        return Work.objects.create(
            owner=self.owner, title="W", desc_ja="d", thumbnail=f"works/{name}"
        )

    def _run(self):
        out = StringIO()
        call_command("migrate_media", stdout=out)
        return out.getvalue()

    def test_所有するユーザーの保存先へ移しthumbnailを更新する(self):
        work = self._legacy_work()
        self.assertIn("移動 1 件", self._run())
        work.refresh_from_db()
        expected = f"users/{self.owner.pk}/works/a.png"
        self.assertEqual(work.thumbnail, expected)
        self.assertTrue((self.root / expected).is_file())
        self.assertFalse((self.root / "works" / "a.png").exists())

    def test_再実行しても変更しない(self):
        work = self._legacy_work()
        self._run()
        self.assertIn("移動 0 件", self._run())
        work.refresh_from_db()
        self.assertEqual(work.thumbnail, f"users/{self.owner.pk}/works/a.png")

    def test_移動済みのファイルはスキップしてthumbnailだけ更新する(self):
        work = self._legacy_work(write=False)
        destination = self.root / f"users/{self.owner.pk}/works/a.png"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"png")
        self.assertIn("移動済み 1 件", self._run())
        work.refresh_from_db()
        self.assertEqual(work.thumbnail, f"users/{self.owner.pk}/works/a.png")

    def test_実体のない参照は更新しない(self):
        work = self._legacy_work(write=False)
        self.assertIn("実体なし 1 件", self._run())
        work.refresh_from_db()
        self.assertEqual(work.thumbnail, "works/a.png")

    def test_ユーザーの保存先や外部URLの参照は対象外(self):
        Work.objects.create(
            owner=self.owner,
            title="X",
            desc_ja="d",
            thumbnail="https://example.com/a.png",
        )
        Work.objects.create(
            owner=self.owner,
            title="Y",
            desc_ja="d",
            thumbnail=f"users/{self.owner.pk}/works/b.png",
        )
        self.assertIn("移動 0 件", self._run())


class UploadStoresUnderUserDirectoryTests(TestCase):
    def test_画像は本人のディレクトリに保存される(self):
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            user = create_user("owner", password="pw-for-test")
            self.client.force_login(user)
            response = self.client.post(
                reverse("manage-api-upload-image"),
                {"image": SimpleUploadedFile("a.png", b"\x89PNG-data")},
            )
            path = response.json()["path"]
            self.assertTrue(path.startswith(f"users/{user.pk}/works/"))
            self.assertTrue((Path(media) / path).is_file())
