"""アカウント画面の API（ユーザー名の変更・公開設定・外部アカウント・退会）のテスト。"""

import json
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portfolio.accounts import SocialAccountAdapter
from portfolio.models import (
    Certification,
    Company,
    Project,
    ReleasedUsername,
    SiteInfo,
    Skill,
    UsageDaily,
    UserProfile,
    Work,
)
from portfolio.tests.helpers import create_user
from portfolio.tests.test_accounts import make_sociallogin


class AccountApiTestCase(TestCase):
    def setUp(self):
        self.user = create_user(
            "taro", password="pw-for-test", email="taro@example.com"
        )
        self.client.force_login(self.user)

    def call(self, method, name, data=None, **kwargs):
        body = json.dumps(data) if data is not None else None
        return getattr(self.client, method)(
            reverse(name, kwargs=kwargs), data=body, content_type="application/json"
        )


class AccountInfoTests(AccountApiTestCase):
    def test_未ログインでは401(self):
        self.client.logout()
        self.assertEqual(self.call("get", "manage-api-account").status_code, 401)

    def test_現在の状態を返す(self):
        self.user.is_staff = True
        self.user.save()
        SocialAccount.objects.create(user=self.user, provider="google", uid="g-1")
        body = self.call("get", "manage-api-account").json()
        self.assertEqual(body["username"], "taro")
        self.assertEqual(body["email"], "taro@example.com")
        self.assertFalse(body["is_public"])
        self.assertEqual(body["public_path"], "/u/taro/")
        self.assertTrue(body["site_name_missing"])
        providers = {p["id"]: p for p in body["providers"]}
        self.assertTrue(providers["google"]["connected"])
        self.assertFalse(providers["github"]["connected"])
        self.assertEqual(providers["github"]["connect_url"], reverse("github_login"))
        self.assertFalse(body["can_disconnect"])

    def test_一般ユーザーには公開設定を返さない(self):
        body = self.call("get", "manage-api-account").json()
        self.assertNotIn("is_public", body)
        self.assertNotIn("public_path", body)


class UsernameChangeTests(AccountApiTestCase):
    def test_ユーザー名を変更でき_旧URLは404になる(self):
        self.user.is_staff = True
        self.user.save()
        self.user.profile.is_public = True
        self.user.profile.save()
        self.assertEqual(self.client.get("/u/taro/").status_code, 200)

        response = self.call("put", "manage-api-account", {"username": "Taro-New"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "taro-new")
        self.assertEqual(response.json()["public_path"], "/u/taro-new/")
        self.assertEqual(self.client.get("/u/taro/").status_code, 404)
        self.assertEqual(self.client.get("/u/taro-new/").status_code, 200)

    def test_旧ユーザー名は予約期間中は他のユーザーが取得できない(self):
        self.call("put", "manage-api-account", {"username": "taro-new"})
        other = create_user("jiro", password="pw-for-test")
        self.client.force_login(other)
        response = self.call("put", "manage-api-account", {"username": "taro"})
        self.assertEqual(response.status_code, 400)

    def test_旧ユーザー名は予約期間を過ぎると他のユーザーが取得できる(self):
        self.call("put", "manage-api-account", {"username": "taro-new"})
        ReleasedUsername.objects.update(released_at=timezone.now() - timedelta(days=91))
        other = create_user("jiro", password="pw-for-test")
        self.client.force_login(other)
        response = self.call("put", "manage-api-account", {"username": "taro"})
        self.assertEqual(response.status_code, 200)

    def test_旧ユーザー名は予約期間中でも本人は取り直せる(self):
        self.call("put", "manage-api-account", {"username": "taro-new"})
        response = self.call("put", "manage-api-account", {"username": "taro"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReleasedUsername.objects.filter(username="taro").exists())
        self.assertTrue(ReleasedUsername.objects.filter(username="taro-new").exists())

    def test_規則に反するユーザー名は変更できない(self):
        create_user("taken")
        for label, username in {
            "予約語": "admin",
            "重複": "TAKEN",
            "形式": "1abc",
            "短い": "ab",
            "空": "",
        }.items():
            with self.subTest(label):
                response = self.call(
                    "put", "manage-api-account", {"username": username}
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.json()["errors"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "taro")

    def test_自分のユーザー名への変更はエラーにならない(self):
        response = self.call("put", "manage-api-account", {"username": "TARO"})
        self.assertEqual(response.status_code, 200)


class PublishSettingTests(AccountApiTestCase):
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save()

    def test_一般ユーザーは公開設定を変更できない(self):
        self.user.is_staff = False
        self.user.save()
        response = self.call("put", "manage-api-account", {"is_public": True})
        self.assertEqual(response.status_code, 400)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.is_public)

    def test_公開と非公開を切り替えられる(self):
        body = self.call("put", "manage-api-account", {"is_public": True}).json()
        self.assertTrue(body["is_public"])
        self.assertEqual(self.client.get("/u/taro/api/certifications").status_code, 200)

        body = self.call("put", "manage-api-account", {"is_public": False}).json()
        self.assertFalse(body["is_public"])
        self.assertEqual(self.client.get("/u/taro/api/certifications").status_code, 404)

    def test_サイト情報の氏名が未入力なら促すための情報を返す(self):
        body = self.call("put", "manage-api-account", {"is_public": True}).json()
        self.assertTrue(body["site_name_missing"])
        SiteInfo.objects.create(
            owner=self.user,
            name="山田 太郎",
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
        self.assertFalse(
            self.call("get", "manage-api-account").json()["site_name_missing"]
        )

    def test_不正な公開設定は拒否する(self):
        response = self.call("put", "manage-api-account", {"is_public": "yes"})
        self.assertEqual(response.status_code, 400)


class ProviderTests(AccountApiTestCase):
    def test_連携が2つあれば解除できる(self):
        SocialAccount.objects.create(user=self.user, provider="google", uid="g-1")
        SocialAccount.objects.create(user=self.user, provider="github", uid="h-1")
        body = self.call(
            "delete", "manage-api-account-provider", provider="github"
        ).json()
        providers = {p["id"]: p["connected"] for p in body["providers"]}
        self.assertEqual(providers, {"google": True, "github": False})
        self.assertFalse(body["can_disconnect"])

    def test_連携が1つだけなら解除できない(self):
        SocialAccount.objects.create(user=self.user, provider="google", uid="g-1")
        response = self.call("delete", "manage-api-account-provider", provider="google")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SocialAccount.objects.filter(user=self.user).count(), 1)

    def test_連携していない提供元は404(self):
        SocialAccount.objects.create(user=self.user, provider="google", uid="g-1")
        SocialAccount.objects.create(user=self.user, provider="github", uid="h-1")
        response = self.call("delete", "manage-api-account-provider", provider="other")
        self.assertEqual(response.status_code, 404)

    def test_他のユーザーの連携は解除できない(self):
        other = create_user("jiro")
        SocialAccount.objects.create(user=other, provider="google", uid="g-2")
        SocialAccount.objects.create(user=other, provider="github", uid="h-2")
        SocialAccount.objects.create(user=self.user, provider="google", uid="g-1")
        response = self.call("delete", "manage-api-account-provider", provider="github")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(SocialAccount.objects.filter(user=other).count(), 2)

    def test_追加連携では他のユーザーへのメールによる紐づけをしない(self):
        # ログイン中のユーザーの追加連携で、同じメールアドレスの別ユーザーに紐づけない。
        other = create_user("jiro", email="shared@example.com")
        login = make_sociallogin(email="shared@example.com", verified=True, uid="g-new")
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = self.client.session

        SocialAccountAdapter().pre_social_login(request, login)

        self.assertFalse(login.is_existing)
        self.assertEqual(SocialAccount.objects.filter(user=other).count(), 0)

    def test_追加連携の完了後は登録画面へ戻る(self):
        self.assertEqual(
            SocialAccountAdapter().get_connect_redirect_url(None, None),
            reverse("manage"),
        )


class WithdrawTests(AccountApiTestCase):
    def setUp(self):
        super().setUp()
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.other = create_user("jiro", password="pw-for-test")

    def _create_data(self, user):
        company = Company.objects.create(
            owner=user, name="社", kind="main", start_year_month="2020-01"
        )
        Project.objects.create(
            owner=user, name="案件", start_year_month="2024-01", company=company
        )
        Certification.objects.create(
            owner=user, name="資格", acquired_on=date(2024, 1, 1), org="X"
        )
        Work.objects.create(owner=user, title="実績", desc_ja="d")
        Skill.objects.create(
            skill_id=f"own-{user.pk}",
            category="言語",
            name="独自",
            sort_order=1,
            owner=user,
        )
        SocialAccount.objects.create(user=user, provider="google", uid=f"g-{user.pk}")
        image = Path(self._media.name) / f"users/{user.pk}/works/a.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"png")
        return image

    def test_ユーザー名の再入力で退会でき_全データと画像が削除される(self):
        image = self._create_data(self.user)
        other_image = self._create_data(self.other)

        response = self.call(
            "post", "manage-api-account-withdraw", {"username": "taro"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect"], reverse("index"))
        self.assertFalse(get_user_model().objects.filter(username="taro").exists())
        for model in (Company, Project, Certification, Work, UserProfile):
            self.assertFalse(
                model.objects.filter(
                    **{
                        (
                            "user_id" if model is UserProfile else "owner_id"
                        ): self.user.pk
                    }
                ).exists(),
                model.__name__,
            )
        self.assertFalse(Skill.objects.filter(skill_id=f"own-{self.user.pk}").exists())
        self.assertFalse(SocialAccount.objects.filter(uid=f"g-{self.user.pk}").exists())
        self.assertFalse(image.exists())
        self.assertFalse(image.parent.parent.exists())
        # セッションは破棄される。
        self.assertNotIn("_auth_user_id", self.client.session)
        # 他のユーザーのデータと画像には影響しない。
        self.assertTrue(other_image.exists())
        self.assertTrue(Project.objects.filter(owner=self.other).exists())
        self.assertTrue(Skill.objects.filter(skill_id=f"own-{self.other.pk}").exists())

    def test_画像の削除に失敗しても退会でき警告を記録する(self):
        def failing_rmtree(path, onexc):
            onexc(None, str(path), PermissionError("denied"))

        with (
            mock.patch("portfolio.account_views.shutil.rmtree", failing_rmtree),
            self.assertLogs("portfolio.account_views", "WARNING") as logs,
        ):
            response = self.call(
                "post", "manage-api-account-withdraw", {"username": "taro"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"user_id={self.user.pk}", logs.output[0])
        self.assertNotIn("taro", logs.output[0])

    def test_退会数のみが集計に加算される(self):
        self.call("post", "manage-api-account-withdraw", {"username": "taro"})
        row = UsageDaily.objects.get(metric=UsageDaily.METRIC_WITHDRAWAL)
        self.assertEqual(row.count, 1)

    def test_ユーザー名が一致しなければ退会できない(self):
        self._create_data(self.user)
        for value in ("", "Taro", "jiro"):
            with self.subTest(value):
                response = self.call(
                    "post", "manage-api-account-withdraw", {"username": value}
                )
                self.assertEqual(response.status_code, 400)
        self.assertTrue(get_user_model().objects.filter(username="taro").exists())
        self.assertTrue(Project.objects.filter(owner=self.user).exists())

    def test_退会したユーザー名は予約され_誰も取得できない(self):
        self.call("post", "manage-api-account-withdraw", {"username": "taro"})
        reservation = ReleasedUsername.objects.get(username="taro")
        self.assertIsNone(reservation.released_by)
        other = create_user("hanako", password="pw-for-test")
        self.client.force_login(other)
        response = self.call("put", "manage-api-account", {"username": "taro"})
        self.assertEqual(response.status_code, 400)

    def test_直近のログインがなければ退会できず再ログインを案内する(self):
        session = self.client.session
        session["authenticated_at"] = int(time.time()) - 11 * 60
        session.save()
        response = self.call(
            "post", "manage-api-account-withdraw", {"username": "taro"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["reauth_required"])
        self.assertTrue(get_user_model().objects.filter(username="taro").exists())

    def test_認証時刻のないセッションでは退会できない(self):
        session = self.client.session
        del session["authenticated_at"]
        session.save()
        response = self.call(
            "post", "manage-api-account-withdraw", {"username": "taro"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(get_user_model().objects.filter(username="taro").exists())

    def test_退会後は同じユーザー名のURLが404になる(self):
        self.user.profile.is_public = True
        self.user.profile.save()
        self.call("post", "manage-api-account-withdraw", {"username": "taro"})
        self.assertEqual(self.client.get("/u/taro/").status_code, 404)

    def test_未ログインでは退会できない(self):
        self.client.logout()
        response = self.call(
            "post", "manage-api-account-withdraw", {"username": "taro"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(get_user_model().objects.filter(username="taro").exists())


class ManageScreenTests(AccountApiTestCase):
    def test_登録画面にアカウントのタブがある(self):
        html = self.client.get(reverse("manage")).content.decode()
        self.assertIn('data-tab="account"', html)
        self.assertIn(reverse("manage-api-account"), html)
