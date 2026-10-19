"""ユニットテスト用設定。MySQL 接続なしで実行できるよう SQLite（メモリ）を使う。"""

import os

os.environ.setdefault("SECRET_KEY", "test-only")
for name in ("GOOGLE", "GITHUB"):
    os.environ.setdefault(f"{name}_CLIENT_ID", f"{name.lower()}-client-id")
    os.environ.setdefault(f"{name}_CLIENT_SECRET", f"{name.lower()}-client-secret")

from .base import *

DEBUG = False

ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
