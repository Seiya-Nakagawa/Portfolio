"""死活監視。直近のサーバーエラー（5xx）の件数を実績 DB に数え、ヘルスチェックの判定に用いる。"""

import contextlib
import time

from django.conf import settings
from django.db import connection

from portfolio import ratelimit
from portfolio.models import RateLimitCounter

SERVER_ERROR_SCOPE = "server_error"
# 件数は 1 分ごとの区間に数え、直近の `HEALTH_ERROR_WINDOW_MINUTES` 分を合計する。
BUCKET_SECONDS = 60


def record_server_error() -> None:
    """サーバーエラー（5xx）を 1 件数える。数えられなくても、元の応答は妨げない。"""
    bucket = int(time.time()) // BUCKET_SECONDS * BUCKET_SECONDS
    # DB 障害時にも元の応答を返すため、数えられなかった場合は無視する。
    with contextlib.suppress(Exception):
        ratelimit.increment(SERVER_ERROR_SCOPE, "all", bucket)


def recent_server_errors() -> int:
    since = int(time.time()) - settings.HEALTH_ERROR_WINDOW_MINUTES * BUCKET_SECONDS
    rows = RateLimitCounter.objects.filter(
        scope=SERVER_ERROR_SCOPE, window_start__gte=since
    ).values_list("count", flat=True)
    return sum(rows)


def database_is_available() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - 接続できない原因を問わず異常とする
        return False


def is_healthy() -> bool:
    """実績 DB に接続でき、直近のサーバーエラーの件数がしきい値以下であれば正常とする。"""
    return (
        database_is_available()
        and recent_server_errors() <= settings.HEALTH_MAX_SERVER_ERRORS
    )
