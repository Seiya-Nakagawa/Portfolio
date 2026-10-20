"""ユーザーごとの保存先（`users/{id}/works/`）の画像ファイルの参照・削除。"""

import time
from pathlib import Path

from django.conf import settings

from portfolio.media_paths import work_image_dir
from portfolio.models import Work


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT)


def user_image_bytes(user_id: int) -> int:
    """ユーザーの保存済み画像の合計バイト数。"""
    directory = _media_root() / work_image_dir(user_id)
    if not directory.is_dir():
        return 0
    return sum(f.stat().st_size for f in directory.iterdir() if f.is_file())


def delete_unreferenced_image(owner, relative: str) -> None:
    """ユーザーの保存先の画像で、どの実績からも参照されていなければ削除する。

    保存先の外やほかのユーザーの画像は対象にしない。
    """
    prefix = f"{work_image_dir(owner.pk)}/"
    if not relative.startswith(prefix) or "/" in relative[len(prefix) :]:
        return
    if Work.objects.filter(thumbnail=relative).exists():
        return
    (_media_root() / relative).unlink(missing_ok=True)


def purge_unreferenced_images(
    grace_seconds: int | None = None, user_id: int | None = None
) -> int:
    """実績から参照されていない画像のうち、更新から猶予を過ぎたものを削除し、件数を返す。

    アップロード後にまだ実績へ保存していない画像を消さないよう、猶予の間は残す。
    `user_id` を指定すると、そのユーザーの保存先のみを対象にする。
    """
    if grace_seconds is None:
        grace_seconds = settings.UNREFERENCED_IMAGE_GRACE_SECONDS
    users_dir = _media_root() / "users"
    if not users_dir.is_dir():
        return 0
    referenced = set(
        Work.objects.filter(thumbnail__startswith="users/").values_list(
            "thumbnail", flat=True
        )
    )
    threshold = time.time() - grace_seconds
    deleted = 0
    pattern = f"{user_id}/works/*" if user_id is not None else "*/works/*"
    for path in users_dir.glob(pattern):
        if not path.is_file() or path.stat().st_mtime > threshold:
            continue
        if path.relative_to(_media_root()).as_posix() in referenced:
            continue
        path.unlink(missing_ok=True)
        deleted += 1
    return deleted
