"""ユーザーごとの画像の保存先（MEDIA_ROOT からの相対パス）。"""

USER_IMAGE_DIR = "users/{user_id}"
WORK_IMAGE_SUBDIR = "works"


def work_image_dir(user_id: int) -> str:
    """ユーザーの実績画像の保存先ディレクトリを返す。"""
    return f"{USER_IMAGE_DIR.format(user_id=user_id)}/{WORK_IMAGE_SUBDIR}"
