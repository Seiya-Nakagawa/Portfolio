"""管理画面からアップロードした画像の保存。git 管理対象外の MEDIA_ROOT 配下へ保存する。"""

import uuid
from pathlib import Path

from django.conf import settings

from portfolio.media_paths import work_image_dir
from portfolio.registry import ValidationFailed

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def save_work_image(user, uploaded) -> str:
    """アップロードされた画像をユーザーの保存先へ保存し、MEDIA_ROOT からの相対パスを返す。"""
    if uploaded is None:
        raise ValidationFailed(["画像ファイルを選択してください。"])
    extension = Path(uploaded.name).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationFailed(
            ["画像は png・jpg・gif・webp のいずれかの形式にしてください。"]
        )
    if uploaded.size > MAX_IMAGE_BYTES:
        raise ValidationFailed(
            [f"画像は {MAX_IMAGE_BYTES // (1024 * 1024)}MB 以下にしてください。"]
        )
    # ファイル名は利用者の入力を使わず、推測されにくい名前を採番する。
    relative = f"{work_image_dir(user.pk)}/{uuid.uuid4().hex}{extension}"
    destination = Path(settings.MEDIA_ROOT) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        for chunk in uploaded.chunks():
            file.write(chunk)
    return relative
