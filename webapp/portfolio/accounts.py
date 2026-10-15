"""外部アカウント（Google・GitHub）によるサインアップ・ログインの処理。"""

import re

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.forms import SignupForm as BaseSocialSignupForm
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from portfolio import usage
from portfolio.models import UsageDaily, UserProfile

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
# 半角英小文字で始まり、半角英小文字・数字・ハイフンからなる。末尾のハイフンと連続するハイフンは不可。
USERNAME_PATTERN = re.compile(r"^[a-z](?:[a-z0-9]|-(?!-))*$")

# サービスのパスや運営上の名称と紛らわしい語。ユーザー名として使えない。
RESERVED_USERNAMES = frozenset(
    {
        "about",
        "account",
        "accounts",
        "admin",
        "administrator",
        "api",
        "app",
        "assets",
        "auth",
        "contact",
        "dashboard",
        "docs",
        "faq",
        "health",
        "healthz",
        "help",
        "index",
        "login",
        "logout",
        "manage",
        "media",
        "null",
        "portfolio",
        "privacy",
        "root",
        "settings",
        "signup",
        "static",
        "staff",
        "support",
        "system",
        "terms",
        "u",
        "undefined",
        "www",
    }
)


def normalize_username(value: str) -> str:
    """入力のユーザー名を小文字に揃える。"""
    return value.strip().lower()


def validate_username(value: str, exclude_user=None) -> str:
    """ユーザー名の規則を検証し、正規化した値を返す。

    Raises:
        ValidationError: 形式・予約語・一意性の規則に反する場合。
    """
    username = normalize_username(value)
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        raise ValidationError(
            f"ユーザー名は{USERNAME_MIN_LENGTH}〜{USERNAME_MAX_LENGTH}文字で入力してください。"
        )
    if not USERNAME_PATTERN.fullmatch(username) or username.endswith("-"):
        raise ValidationError(
            "ユーザー名は半角英小文字で始め、半角英小文字・数字・ハイフンで入力してください"
            "（末尾のハイフンと連続するハイフンは使えません）。"
        )
    if username in RESERVED_USERNAMES:
        raise ValidationError("このユーザー名は使用できません。")
    taken = get_user_model().objects.filter(username__iexact=username)
    if exclude_user is not None:
        taken = taken.exclude(pk=exclude_user.pk)
    if taken.exists():
        raise ValidationError("このユーザー名は既に使われています。")
    return username


class AccountAdapter(DefaultAccountAdapter):
    def clean_username(self, username, shallow=False):
        return validate_username(username)

    def is_open_for_signup(self, request):
        # 外部アカウント経由のサインアップのみ受け付ける（ローカルのサインアップ画面は提供しない）。
        return True


def _stopped_response(request):
    return ImmediateHttpResponse(render(request, "account/stopped.html", status=403))


def _verified_emails(sociallogin) -> list[str]:
    return [a.email for a in sociallogin.email_addresses if a.verified and a.email]


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """既存ユーザーとの紐づけと、利用停止中のユーザーのログイン拒否を行う。"""
        if request.user.is_authenticated:
            # ログイン中のユーザーによる追加連携。メールアドレスによる他のユーザーへの紐づけは行わない。
            return
        if not sociallogin.is_existing:
            user = self._find_user_by_verified_email(sociallogin)
            if user is None:
                return
            if not user.is_active:
                raise _stopped_response(request)
            sociallogin.connect(request, user)
            return
        if not sociallogin.user.is_active:
            raise _stopped_response(request)

    def get_connect_redirect_url(self, request, socialaccount):
        """追加連携の完了後は、アカウント画面を含む登録画面へ戻る。"""
        return reverse("manage")

    @staticmethod
    def _find_user_by_verified_email(sociallogin):
        """提供元が検証済みとしているメールアドレスに一致する既存ユーザーを返す。

        未検証のメールアドレスでは紐づけない（他人のアカウントの乗っ取りを防ぐ）。
        一致するユーザーが 1 人に定まらない場合も紐づけない。
        """
        users = get_user_model().objects
        found = set()
        for email in _verified_emails(sociallogin):
            found.update(users.filter(email__iexact=email).values_list("pk", flat=True))
        if len(found) != 1:
            return None
        return users.get(pk=found.pop())

    def save_user(self, request, sociallogin, form=None):
        """ユーザーを作成し、プロフィール（同意した規約の版）と登録数の集計を記録する。"""
        with transaction.atomic():
            user = super().save_user(request, sociallogin, form)
            # 提供元が検証済みとしていないメールアドレスは保存しない。
            # 保存すると、後からそのアドレスを検証済みで持つ別の外部アカウントが、
            # このユーザーに自動で紐づけられてしまう（アカウントの乗っ取り）。
            verified = {e.lower() for e in _verified_emails(sociallogin)}
            if user.email and user.email.lower() not in verified:
                user.email = ""
                user.save(update_fields=["email"])
            UserProfile.objects.create(
                user=user,
                is_public=False,
                terms_version=settings.TERMS_VERSION,
                privacy_version=settings.PRIVACY_VERSION,
                agreed_at=timezone.now(),
            )
            usage.increment(UsageDaily.METRIC_SIGNUP)
        return user


class SignupForm(BaseSocialSignupForm):
    """ユーザー名の入力と、利用規約・プライバシーポリシーへの同意を求めるサインアップ。"""

    agree = forms.BooleanField(
        required=True,
        error_messages={
            "required": "利用規約とプライバシーポリシーに同意してください。"
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # メールアドレスは外部アカウントから取得した値のまま変更させない。
        self.fields["email"].disabled = True


class ReconsentForm(forms.Form):
    """改定された利用規約・プライバシーポリシーへの再同意。"""

    agree = forms.BooleanField(
        required=True,
        error_messages={"required": "同意する場合はチェックを入れてください。"},
    )


def has_agreed_to_current_terms(user) -> bool:
    """同意した規約・プライバシーポリシーの版が、どちらも現行かを返す。"""
    profile = UserProfile.objects.filter(user=user).first()
    return (
        profile is not None
        and profile.terms_version == settings.TERMS_VERSION
        and profile.privacy_version == settings.PRIVACY_VERSION
    )


def record_agreement(user) -> None:
    """現行の版への同意を記録する。プロフィールがなければ作成する。"""
    UserProfile.objects.update_or_create(
        user=user,
        defaults={
            "terms_version": settings.TERMS_VERSION,
            "privacy_version": settings.PRIVACY_VERSION,
            "agreed_at": timezone.now(),
        },
    )
