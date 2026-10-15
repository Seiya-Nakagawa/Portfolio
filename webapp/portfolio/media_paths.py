"""ユーザーごとの画像の保存先（MEDIA_ROOT からの相対パス）。"""

import re

USER_IMAGE_DIR = "users/{user_id}"
WORK_IMAGE_SUBDIR = "works"


def work_image_dir(user_id: int) -> str:
    """ユーザーの実績画像の保存先ディレクトリを返す。"""
    return f"{USER_IMAGE_DIR.format(user_id=user_id)}/{WORK_IMAGE_SUBDIR}"


# 配信・指定を許可する画像のパス。ディレクトリ名とファイル名は英数字・アンダースコア・ハイフンに限り、
# 「..」や「//」を含めない（配信時に正規化されて別のユーザーのファイルを指すのを防ぐ）。
USER_IMAGE_PATH = re.compile(
    r"^users/(?P<user_id>\d+)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.[A-Za-z0-9]+$"
)
