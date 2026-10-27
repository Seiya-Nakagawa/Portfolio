"""流量制限・画像の形式判定と容量上限・不要な画像の削除のテスト。"""

import os
import tempfile
import time
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from portfolio import media_files, ratelimit
from portfolio.models import RateLimitCounter, Work
from portfolio.tests.helpers import create_user

PNG = b"\x89PNG\r\n\x1a\n"
JPEG = b"\xff\xd8\xff\xe0"
GIF = b"GIF89a"
WEBP = b"RIFF\x00\x00\x00\x00WEBP"


class ClientIpTests(TestCase):
    def ip(self, forwarded=None, **settings_):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=forwarded or ""
        )
        with override_settings(**settings_):
            return ratelimit.client_ip(request)

    def test_without_proxy_uses_remote_addr(self):
        self.assertEqual(self.ip("1.1.1.1", TRUSTED_PROXY_COUNT=0), "10.0.0.1")

    def test_uses_value_appended_by_ingress(self):
        # 先頭は接続元が任意に付与できるため、末尾（Ingress が付与した値）を用いる。
        self.assertEqual(
            self.ip("6.6.6.6, 203.0.113.9", TRUSTED_PROXY_COUNT=1), "203.0.113.9"
        )

    def test_missing_header_falls_back_to_remote_addr(self):
        self.assertEqual(self.ip(None, TRUSTED_PROXY_COUNT=1), "10.0.0.1")


@override_settings(
    RATE_LIMITS={"public": (3, 60), "login": (2, 60), "pdf": (1, 60), "upload": (1, 60)}
)
class RateLimitTests(TestCase):
    def test_public_pages_are_limited_per_ip(self):
        for _ in range(3):
            self.assertEqual(self.client.get("/u/nobody/").status_code, 404)
        response = self.client.get("/u/nobody/")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    def test_other_ip_is_not_affected(self):
        for _ in range(4):
            self.client.get("/u/nobody/", REMOTE_ADDR="192.0.2.1")
        self.assertEqual(
            self.client.get("/u/nobody/", REMOTE_ADDR="192.0.2.2").status_code, 404
        )

    def test_login_is_limited(self):
        statuses = [self.client.get(reverse("login")).status_code for _ in range(3)]
        self.assertEqual(statuses, [200, 200, 429])

    def test_counter_does_not_store_raw_ip(self):
        self.client.get("/u/nobody/", REMOTE_ADDR="192.0.2.1")
        self.assertNotIn("192.0.2.1", RateLimitCounter.objects.get().identifier)

    def test_pdf_is_limited_per_user(self):
        user = create_user("taro", is_staff=True)
        other = create_user("hanako", is_staff=True)
        self.assertTrue(ratelimit.hit("pdf", str(user.pk)))
        self.client.force_login(user)
        response = self.client.get(reverse("manage-skillsheet-pdf"))
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertTrue(ratelimit.hit("pdf", str(other.pk)))

    def test_upload_is_limited_per_user(self):
        user = create_user("taro", is_staff=True)
        self.client.force_login(user)
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            first = self.client.post(
                reverse("manage-api-upload-image"),
                {"image": SimpleUploadedFile("a.png", PNG + b"x")},
            )
            second = self.client.post(
                reverse("manage-api-upload-image"),
                {"image": SimpleUploadedFile("a.png", PNG + b"x")},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_purge_expired_removes_old_rows_only(self):
        ratelimit.hit("public", "x")
        RateLimitCounter.objects.create(
            scope="public", identifier="old", window_start=1, count=1
        )
        self.assertEqual(ratelimit.purge_expired(), 1)
        self.assertEqual(RateLimitCounter.objects.count(), 1)


class MediaTestCase(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = create_user("taro", is_staff=True)
        self.client.force_login(self.user)
        self.root = Path(self._media.name)

    def upload(self, name, content):
        return self.client.post(
            reverse("manage-api-upload-image"),
            {"image": SimpleUploadedFile(name, content)},
        )


class ImageFormatTests(MediaTestCase):
    def test_extension_follows_content(self):
        cases = [(PNG, ".png"), (JPEG, ".jpg"), (GIF, ".gif"), (WEBP, ".webp")]
        for header, extension in cases:
            response = self.upload("picture.png", header + b"data")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["path"].endswith(extension))

    def test_non_image_content_is_rejected(self):
        for name in ("a.png", "a.jpg", "a.webp"):
            response = self.upload(name, b"<script>alert(1)</script>")
            self.assertEqual(response.status_code, 400)

    def test_svg_is_rejected(self):
        self.assertEqual(self.upload("a.svg", b"<svg></svg>").status_code, 400)


class QuotaTests(MediaTestCase):
    @override_settings(MAX_USER_IMAGE_BYTES=100)
    def test_total_size_is_limited_per_user(self):
        self.assertEqual(self.upload("a.png", PNG + b"x" * 60).status_code, 200)
        self.assertEqual(self.upload("b.png", PNG + b"x" * 60).status_code, 400)
        other = create_user("hanako", is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.upload("c.png", PNG + b"x" * 60).status_code, 200)

    @override_settings(MAX_USER_IMAGE_BYTES=100)
    def test_old_unsaved_images_are_reclaimed_when_over_quota(self):
        path = self.upload("a.png", PNG + b"x" * 70).json()["path"]
        file = Path(settings.MEDIA_ROOT) / path
        # 直後の未保存の画像は残り、容量超過のまま。
        self.assertEqual(self.upload("b.png", PNG + b"x" * 70).status_code, 400)
        self.assertTrue(file.exists())
        # 一定時間を過ぎた未保存の画像は整理され、アップロードできる。
        old = time.time() - 2 * 60 * 60
        os.utime(file, (old, old))
        self.assertEqual(self.upload("b.png", PNG + b"x" * 70).status_code, 200)
        self.assertFalse(file.exists())

    @override_settings(MAX_USER_IMAGE_BYTES=100)
    def test_deleting_work_frees_quota(self):
        path = self.upload("a.png", PNG + b"x" * 70).json()["path"]
        work = Work.objects.create(owner=self.user, title="t", thumbnail=path)
        self.assertEqual(self.upload("b.png", PNG + b"x" * 70).status_code, 400)
        self.client.delete(reverse("manage-api-work", args=[work.pk]))
        self.assertEqual(self.upload("b.png", PNG + b"x" * 70).status_code, 200)


class ImageCleanupTests(MediaTestCase):
    def make_work(self, path):
        return Work.objects.create(owner=self.user, title="t", thumbnail=path)

    def test_deleting_work_removes_its_image(self):
        path = self.upload("a.png", PNG + b"x").json()["path"]
        work = self.make_work(path)
        self.client.delete(reverse("manage-api-work", args=[work.pk]))
        self.assertFalse((self.root / path).exists())

    def test_image_still_referenced_is_kept(self):
        path = self.upload("a.png", PNG + b"x").json()["path"]
        work = self.make_work(path)
        self.make_work(path)
        self.client.delete(reverse("manage-api-work", args=[work.pk]))
        self.assertTrue((self.root / path).exists())

    def test_replacing_image_removes_the_old_one(self):
        old = self.upload("a.png", PNG + b"x").json()["path"]
        new = self.upload("b.png", PNG + b"y").json()["path"]
        work = self.make_work(old)
        response = self.client.put(
            reverse("manage-api-work", args=[work.pk]),
            {"title": "t", "desc_ja": "d", "thumbnail": new, "achieved_on": "2024-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse((self.root / old).exists())
        self.assertTrue((self.root / new).exists())

    def test_files_outside_user_directory_are_not_deleted(self):
        outside = self.root / "keep.txt"
        outside.write_text("x")
        media_files.delete_unreferenced_image(self.user, "keep.txt")
        media_files.delete_unreferenced_image(
            self.user, f"users/{self.user.pk}/works/../../../keep.txt"
        )
        self.assertTrue(outside.exists())

    def test_daily_job_removes_only_stale_unreferenced_images(self):
        kept = self.upload("a.png", PNG + b"1").json()["path"]
        self.make_work(kept)
        stale = self.upload("b.png", PNG + b"2").json()["path"]
        fresh = self.upload("c.png", PNG + b"3").json()["path"]
        day_ago = time.time() - 2 * 24 * 60 * 60
        for path in (kept, stale):
            os.utime(self.root / path, (day_ago, day_ago))
        out = StringIO()
        call_command("daily_maintenance", stdout=out)
        self.assertTrue((self.root / kept).exists())
        self.assertFalse((self.root / stale).exists())
        self.assertTrue((self.root / fresh).exists())
        self.assertIn("未使用の画像 1 件", out.getvalue())
