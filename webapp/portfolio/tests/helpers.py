import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from portfolio.models import UserProfile


def create_user(username: str | None = None, agreed: bool = True, **kwargs):
    """テスト用ユーザーを作成する。ユーザー名を省略すると重複しない名前を採番する。

    既定では現行の利用規約・プライバシーポリシーに同意済みのプロフィールを持つ。
    """
    username = username or f"user-{uuid.uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(username, **kwargs)
    if agreed:
        UserProfile.objects.create(
            user=user,
            terms_version=settings.TERMS_VERSION,
            privacy_version=settings.PRIVACY_VERSION,
            agreed_at=timezone.now(),
        )
    return user


def create_operator(username: str = "operator"):
    """公開ポートフォリオの表示対象となる運営者を作成する。"""
    return create_user(username, is_staff=True)
