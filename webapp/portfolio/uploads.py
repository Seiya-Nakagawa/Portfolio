"""管理画面からアップロードした画像の保存。git 管理対象外の MEDIA_ROOT 配下へ保存する。"""

import uuid
from pathlib import Path

from django.conf import settings

from portfolio.media_files import user_image_bytes
from portfolio.media_paths import work_image_dir
from portfolio.registry import ValidationFailed

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def detect_image_extension(header: bytes) -> str | None:
    """ファイルの先頭のバイト列から画像の形式を判定し、保存に用いる拡張子を返す。"""
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


def _megabytes(size: int) -> int:
    return size // (1024 * 1024)


def save_work_image(user, uploaded) -> str:
    """アップロードされた画像をユーザーの保存先へ保存し、MEDIA_ROOT からの相対パスを返す。"""
    if uploaded is None:
        raise ValidationFailed(["画像ファイルを選択してください。"])
    format_error = ["画像は png・jpg・gif・webp のいずれかの形式にしてください。"]
    if Path(uploaded.name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationFailed(format_error)
    # 拡張子は利用者が自由に付けられるため、内容から形式を判定して保存する拡張子を決める。
    uploaded.seek(0)
    extension = detect_image_extension(uploaded.read(12))
    uploaded.seek(0)
    if extension is None:
        raise ValidationFailed(format_error)
    if uploaded.size > settings.MAX_IMAGE_BYTES:
        raise ValidationFailed(
            [f"画像は {_megabytes(settings.MAX_IMAGE_BYTES)}MB 以下にしてください。"]
        )
    if user_image_bytes(user.pk) + uploaded.size > settings.MAX_USER_IMAGE_BYTES:
        limit = _megabytes(settings.MAX_USER_IMAGE_BYTES)
        raise ValidationFailed(
            [
                f"保存できる画像の合計は {limit}MB までです。不要な画像を削除してください。"
            ]
        )
    # ファイル名は利用者の入力を使わず、推測されにくい名前を採番する。
    relative = f"{work_image_dir(user.pk)}/{uuid.uuid4().hex}{extension}"
    destination = Path(settings.MEDIA_ROOT) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        for chunk in uploaded.chunks():
            file.write(chunk)
    return relative
