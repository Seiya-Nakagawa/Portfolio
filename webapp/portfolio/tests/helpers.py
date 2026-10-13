import uuid

from django.contrib.auth import get_user_model


def create_user(username: str | None = None, **kwargs):
    """パスワードを持たないテスト用ユーザーを作成する。ユーザー名を省略すると重複しない名前を採番する。"""
    username = username or f"user-{uuid.uuid4().hex[:8]}"
    return get_user_model().objects.create_user(username, **kwargs)


def create_operator(username: str = "operator"):
    """公開ポートフォリオの表示対象となる運営者を作成する。"""
    return create_user(username, is_staff=True)
