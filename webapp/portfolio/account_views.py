"""アカウント画面の JSON API。ユーザー名の変更・公開設定・外部アカウントの連携・退会。"""

import logging
import shutil
from pathlib import Path

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse

from portfolio import registry, usage
from portfolio.accounts import (
    forget_reservation,
    has_recent_login,
    release_username,
    validate_username,
)
from portfolio.manage_views import _body, _json, api_view
from portfolio.media_paths import USER_IMAGE_DIR
from portfolio.models import SiteInfo, UsageDaily, UserProfile

logger = logging.getLogger(__name__)

# 連携できる提供元。表示順に並べる。
PROVIDERS = [("google", "Google"), ("github", "GitHub")]


def _profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _account_payload(request) -> dict:
    user = request.user
    linked = set(
        SocialAccount.objects.filter(user=user).values_list("provider", flat=True)
    )
    return {
        "username": user.username,
        "email": user.email,
        "is_public": _profile(user).is_public,
        "public_path": reverse("portfolio", args=[user.username]),
        "site_name_missing": not SiteInfo.objects.for_owner(user)
        .exclude(name="")
        .exists(),
        "providers": [
            {
                "id": provider_id,
                "name": name,
                "connected": provider_id in linked,
                "connect_url": reverse(f"{provider_id}_login"),
            }
            for provider_id, name in PROVIDERS
        ],
        "can_disconnect": len(linked) > 1,
    }


@api_view("GET", "PUT")
def api_account(request):
    """アカウント情報の取得と、ユーザー名・公開設定の変更。"""
    if request.method == "PUT":
        _update_account(request.user, _body(request))
    return _json(_account_payload(request))


def _update_account(user, body: dict) -> None:
    errors = []
    new_username = None
    if "username" in body:
        try:
            new_username = validate_username(
                str(body["username"] or ""), exclude_user=user
            )
        except ValidationError as error:
            errors.extend(error.messages)
    if "is_public" in body and not isinstance(body["is_public"], bool):
        errors.append("公開設定の形式が不正です。")
    if errors:
        raise registry.ValidationFailed(errors)

    with transaction.atomic():
        if new_username is not None and new_username != user.username:
            # 旧ユーザー名は一定期間予約し、他のユーザーが取得できないようにする。
            release_username(user.username, user.pk)
            forget_reservation(new_username)
            user.username = new_username
            user.save(update_fields=["username"])
        if "is_public" in body:
            profile = _profile(user)
            profile.is_public = body["is_public"]
            profile.save(update_fields=["is_public"])


@api_view("DELETE")
def api_account_provider(request, provider):
    """外部アカウントの連携を解除する。紐づけが 1 つだけの場合は解除できない。"""
    with transaction.atomic():
        accounts = SocialAccount.objects.select_for_update().filter(user=request.user)
        linked = list(accounts)
        target = next((a for a in linked if a.provider == provider), None)
        if target is None:
            raise registry.NotFound("連携している外部アカウントが見つかりません。")
        if len(linked) <= 1:
            raise registry.ValidationFailed(
                ["連携が 1 つだけの場合は解除できません（ログインできなくなります）。"]
            )
        target.delete()
    return _json(_account_payload(request))


@api_view("POST")
def api_account_withdraw(request):
    """退会する。直近のログインとユーザー名の再入力が一致した場合のみ、全データと画像を削除する。"""
    user = request.user
    if not has_recent_login(request):
        return _json(
            {
                "errors": [
                    "退会には直近のログインが必要です。再ログインしてください。"
                ],
                "reauth_required": True,
            },
            status=403,
        )
    confirmation = str(_body(request).get("username") or "").strip()
    if confirmation != user.username:
        raise registry.ValidationFailed(["確認用のユーザー名が一致しません。"])

    user_id = user.pk
    # データベースの削除は 1 トランザクションで行う。所有する行は連鎖して削除される。
    with transaction.atomic():
        username = user.username
        user.delete()
        # 解放したユーザー名は一定期間予約する（退会したユーザーを特定する情報は残さない）。
        release_username(username, None)
        # 退会したユーザーを特定できる情報は残さず、退会数のみを加算する。
        usage.increment(UsageDaily.METRIC_WITHDRAWAL)

    # トランザクションの確定後に、画像の保存先を削除する。
    shutil.rmtree(
        Path(settings.MEDIA_ROOT) / USER_IMAGE_DIR.format(user_id=user_id),
        onexc=lambda _func, _path, exc: logger.warning(
            "退会したユーザーの画像を削除できませんでした。user_id=%s error=%s",
            user_id,
            type(exc).__name__,
        ),
    )
    logout(request)
    return _json({"ok": True, "redirect": reverse("index")})
