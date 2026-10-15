"""外部アカウント（Google・GitHub）による認証、サインアップ、規約への同意のテスト。"""

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portfolio import usage
from portfolio.accounts import (
    RESERVED_USERNAMES,
    SocialAccountAdapter,
    has_agreed_to_current_terms,
    validate_username,
)
from portfolio.models import UsageDaily, UserProfile
from portfolio.tests.helpers import create_user

SESSION_KEY = "socialaccount_sociallogin"


def make_sociallogin(email="new@example.com", verified=True, uid="uid-1"):
    """外部アカウント（Google）の認可が成功した直後の状態（未保存）を作る。"""
    request = RequestFactory().get("/")
    request.session = {}
    provider = get_adapter().get_provider(request, "google")
    return provider.sociallogin_from_response(
        request,
        {
            "sub": uid,
            "email": email,
            "email_verified": verified,
            "given_name": "太郎",
            "family_name": "山田",
            "name": "山田 太郎",
        },
    )


class ValidateUsernameTests(TestCase):
    def test_有効なユーザー名は小文字に揃えて返す(self):
        self.assertEqual(validate_username("Taro-123"), "taro-123")
        self.assertEqual(validate_username("abc"), "abc")
        self.assertEqual(validate_username("a" * 30), "a" * 30)

    def test_規則に反するユーザー名は拒否する(self):
        invalid = {
            "短すぎる": "ab",
            "長すぎる": "a" * 31,
            "数字で始まる": "1abc",
            "ハイフンで始まる": "-abc",
            "末尾のハイフン": "abc-",
            "連続するハイフン": "a--b",
            "アンダースコア": "a_b",
            "全角": "ａｂｃ",
            "空白を含む": "a b",
        }
        for label, value in invalid.items():
            with self.subTest(label), self.assertRaises(ValidationError):
                validate_username(value)

    def test_予約語は使えない(self):
        for word in (
            "admin",
            "api",
            "manage",
            "accounts",
            "static",
            "media",
            "u",
            "terms",
            "privacy",
            "support",
        ):
            with self.subTest(word):
                self.assertIn(word, RESERVED_USERNAMES)
                with self.assertRaises(ValidationError):
                    validate_username(word)
        with self.assertRaises(ValidationError):
            validate_username("ADMIN")

    def test_大文字小文字を区別せず重複を拒否する(self):
        create_user("Taro")
        with self.assertRaises(ValidationError):
            validate_username("taro")

    def test_自分自身のユーザー名は重複とみなさない(self):
        user = create_user("taro")
        self.assertEqual(validate_username("TARO", exclude_user=user), "taro")


class LoginPageTests(TestCase):
    def test_GoogleとGitHubのボタンのみでパスワード欄を持たない(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(reverse("google_login"), html)
        self.assertIn(reverse("github_login"), html)
        self.assertNotIn('type="password"', html)

    def test_パスワードによるログインはできない(self):
        create_user("taro", password="pw-for-test")
        response = self.client.post(
            reverse("login"), {"username": "taro", "password": "pw-for-test"}
        )
        self.assertEqual(response.status_code, 405)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_ログイン済みなら登録画面へ移動する(self):
        user = create_user("taro")
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("login")),
            reverse("manage"),
            fetch_redirect_response=False,
        )

    def test_管理サイトのログインは本サービスのログイン画面へ誘導する(self):
        response = self.client.get("/admin/login/?next=/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))

    def test_未ログインの登録画面はログイン画面へ誘導する(self):
        response = self.client.get(reverse("manage"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('manage')}",
            fetch_redirect_response=False,
        )


class PreSocialLoginTests(TestCase):
    def setUp(self):
        self.adapter = SocialAccountAdapter()
        self.request = RequestFactory().get("/")
        self.request.session = self.client.session
        self.request.user = AnonymousUser()

    def test_検証済みのメールアドレスが一致すれば既存ユーザーに紐づける(self):
        user = create_user("taro", email="Taro@example.com")
        login = make_sociallogin(email="taro@example.com", verified=True)

        self.adapter.pre_social_login(self.request, login)

        self.assertEqual(login.user, user)
        self.assertTrue(login.is_existing)
        self.assertEqual(SocialAccount.objects.get().user, user)

    def test_未検証のメールアドレスでは紐づけない(self):
        create_user("taro", email="taro@example.com")
        login = make_sociallogin(email="taro@example.com", verified=False)

        self.adapter.pre_social_login(self.request, login)

        self.assertFalse(login.is_existing)
        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_一致するユーザーがいなければ紐づけない(self):
        login = make_sociallogin(email="nobody@example.com")
        self.adapter.pre_social_login(self.request, login)
        self.assertFalse(login.is_existing)

    def test_一致するユーザーが複数いれば紐づけない(self):
        create_user("taro", email="dup@example.com")
        create_user("jiro", email="dup@example.com")
        login = make_sociallogin(email="dup@example.com")
        self.adapter.pre_social_login(self.request, login)
        self.assertFalse(login.is_existing)

    def test_利用停止中のユーザーには紐づけずログインを拒否する(self):
        user = create_user("taro", email="taro@example.com")
        user.is_active = False
        user.save()
        login = make_sociallogin(email="taro@example.com")

        with self.assertRaises(ImmediateHttpResponse) as raised:
            self.adapter.pre_social_login(self.request, login)

        self.assertEqual(raised.exception.response.status_code, 403)
        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_紐づけ済みの利用停止中のユーザーはログインを拒否する(self):
        user = create_user("taro")
        user.is_active = False
        user.save()
        SocialAccount.objects.create(user=user, provider="google", uid="uid-1")
        login = make_sociallogin(uid="uid-1")
        self.assertTrue(login.lookup() is None or login.is_existing)

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, login)


class SignupTests(TestCase):
    def _start(self, **kwargs):
        """外部アカウントの認可が成功した状態でサインアップ画面を開ける状態にする。"""
        session = self.client.session
        session[SESSION_KEY] = make_sociallogin(**kwargs).serialize()
        session.save()

    def _post(self, **data):
        return self.client.post(reverse("socialaccount_signup"), data)

    def test_サインアップ画面に表示名とメールアドレスを表示する(self):
        self._start()
        response = self.client.get(reverse("socialaccount_signup"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("new@example.com", html)
        self.assertIn("山田", html)

    def test_ユーザー名と同意でユーザーとプロフィールが作成される(self):
        self._start()

        response = self._post(username="Taro-Yamada", agree="on")

        self.assertRedirects(response, reverse("manage"), fetch_redirect_response=False)
        user = get_user_model().objects.get()
        self.assertEqual(user.username, "taro-yamada")
        self.assertEqual(user.email, "new@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(profile.is_public)
        self.assertEqual(profile.terms_version, settings.TERMS_VERSION)
        self.assertEqual(profile.privacy_version, settings.PRIVACY_VERSION)
        self.assertIsNotNone(profile.agreed_at)
        self.assertEqual(SocialAccount.objects.get().user, user)
        self.assertEqual(
            UsageDaily.objects.get(metric=UsageDaily.METRIC_SIGNUP).count, 1
        )

    def test_未検証のメールアドレスはユーザーに保存しない(self):
        self._start(email="victim@example.com", verified=False)

        self._post(username="attacker", agree="on")

        user = get_user_model().objects.get()
        self.assertEqual(user.email, "")
        # 後から被害者が検証済みの同じアドレスでログインしても、紐づかない。
        self.assertIsNone(
            SocialAccountAdapter._find_user_by_verified_email(
                make_sociallogin(email="victim@example.com", uid="uid-victim")
            )
        )

    def test_同意しなければ登録できない(self):
        self._start()
        response = self._post(username="taro")
        self.assertEqual(response.status_code, 200)
        self.assertIn("同意してください", response.content.decode())
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(UserProfile.objects.count(), 0)

    def test_規則に反するユーザー名では登録できない(self):
        create_user("taken")
        for label, username in {
            "予約語": "admin",
            "重複": "TAKEN",
            "形式": "1abc",
            "短い": "ab",
        }.items():
            with self.subTest(label):
                self._start(uid=f"uid-{label}")
                response = self._post(username=username, agree="on")
                self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_利用停止中の既存ユーザーとはサインアップさせない(self):
        # 検証済みメールアドレスが一致する停止中のユーザーがいる場合は、ログインを拒否する。
        user = create_user("taro", email="new@example.com")
        user.is_active = False
        user.save()
        adapter = SocialAccountAdapter()
        request = RequestFactory().get("/")
        request.session = self.client.session
        request.user = AnonymousUser()
        with self.assertRaises(ImmediateHttpResponse):
            adapter.pre_social_login(request, make_sociallogin())

    def test_サインアップに失敗した場合は集計もユーザーも残らない(self):
        self._start()
        self._post(username="admin", agree="on")
        self.assertEqual(UsageDaily.objects.count(), 0)


class ReconsentTests(TestCase):
    def setUp(self):
        self.user = create_user("taro")
        self.client.force_login(self.user)

    def _outdate(self, **fields):
        UserProfile.objects.filter(user=self.user).update(**fields)

    def test_現行の版に同意済みなら画面を表示できる(self):
        self.assertTrue(has_agreed_to_current_terms(self.user))
        self.assertEqual(self.client.get(reverse("manage")).status_code, 200)

    def test_利用規約の版が古ければ再同意画面へ誘導する(self):
        self._outdate(terms_version="2000-01-01")
        response = self.client.get(reverse("manage"))
        self.assertRedirects(
            response,
            f"{reverse('reconsent')}?next={reverse('manage')}",
            fetch_redirect_response=False,
        )

    def test_プライバシーポリシーの版が古くても誘導する(self):
        self._outdate(privacy_version="")
        self.assertEqual(self.client.get(reverse("manage")).status_code, 302)

    def test_プロフィールがなければ誘導する(self):
        UserProfile.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.get(reverse("manage")).status_code, 302)

    def test_管理画面のAPIも再同意まで利用できない(self):
        self._outdate(terms_version="2000-01-01")
        response = self.client.get(reverse("manage-api-bootstrap"))
        self.assertEqual(response.status_code, 302)

    def test_再同意画面_ログアウト_規約の閲覧は誘導の対象外(self):
        self._outdate(terms_version="2000-01-01")
        self.assertEqual(self.client.get(reverse("reconsent")).status_code, 200)
        self.assertEqual(self.client.get(reverse("terms")).status_code, 200)
        self.assertEqual(self.client.get(reverse("privacy")).status_code, 200)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("index"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_同意すると記録して元の画面へ戻る(self):
        self._outdate(terms_version="2000-01-01", privacy_version="2000-01-01")
        response = self.client.post(
            reverse("reconsent"), {"agree": "on", "next": reverse("manage")}
        )
        self.assertRedirects(response, reverse("manage"), fetch_redirect_response=False)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.terms_version, settings.TERMS_VERSION)
        self.assertEqual(profile.privacy_version, settings.PRIVACY_VERSION)
        self.assertEqual(self.client.get(reverse("manage")).status_code, 200)

    def test_チェックなしでは同意できない(self):
        self._outdate(terms_version="2000-01-01")
        response = self.client.post(reverse("reconsent"), {"next": reverse("manage")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserProfile.objects.get().terms_version, "2000-01-01")

    def test_外部サイトへの戻り先は無視する(self):
        self._outdate(terms_version="2000-01-01")
        response = self.client.post(
            reverse("reconsent"), {"agree": "on", "next": "https://evil.example.com/"}
        )
        self.assertRedirects(response, reverse("manage"), fetch_redirect_response=False)

    def test_規約の改定で全ユーザーが再同意の対象になる(self):
        with override_settings(TERMS_VERSION="2099-01-01"):
            self.assertFalse(has_agreed_to_current_terms(self.user))
            self.assertEqual(self.client.get(reverse("manage")).status_code, 302)

    def test_未ログインのユーザーは誘導されない(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("terms")).status_code, 200)
        self.assertEqual(self.client.get(reverse("index")).status_code, 200)


class InactiveUserTests(TestCase):
    def test_利用停止にすると既存のセッションも無効になる(self):
        user = create_user("taro")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("manage")).status_code, 200)

        user.is_active = False
        user.save()

        response = self.client.get(reverse("manage"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('manage')}",
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.get(reverse("manage-api-bootstrap")).status_code, 401
        )


class UsageIncrementTests(TestCase):
    def test_初回は作成し_以降は加算する(self):
        usage.increment(UsageDaily.METRIC_SIGNUP)
        usage.increment(UsageDaily.METRIC_SIGNUP)
        usage.increment(UsageDaily.METRIC_SKILLSHEET_PDF)
        today = timezone.localdate()
        self.assertEqual(
            UsageDaily.objects.get(usage_date=today, metric="signup").count, 2
        )
        self.assertEqual(
            UsageDaily.objects.get(usage_date=today, metric="skillsheet_pdf").count, 1
        )
