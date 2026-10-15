"""流量制限。回数は実績 DB（`rate_limit_counters`）で共有し、固定の時間区間ごとに数える。"""

import hashlib
import time

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F

from portfolio.models import RateLimitCounter

# 区間の終了後、整理処理で削除するまでに残す秒数。
RETENTION_SECONDS = 24 * 60 * 60


def client_ip(request) -> str:
    """接続元の IP アドレスを返す。

    共有 Ingress が付与する X-Forwarded-For の末尾から `TRUSTED_PROXY_COUNT` 番目の値を用いる。
    それより前の値は接続元が任意に付与できるため信用しない。
    """
    proxies = settings.TRUSTED_PROXY_COUNT
    if proxies > 0:
        forwarded = [
            part.strip()
            for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            if part.strip()
        ]
        if len(forwarded) >= proxies:
            return forwarded[-proxies]
    return request.META.get("REMOTE_ADDR", "")


def _hash(value: str) -> str:
    return hashlib.sha256(f"{settings.SECRET_KEY}:{value}".encode()).hexdigest()


def increment(scope: str, identifier: str, window_start: int) -> int:
    """区間の回数を 1 加算し、加算後の回数を返す。当日の行がなければ作成する。"""
    queryset = RateLimitCounter.objects.filter(
        scope=scope, identifier=_hash(identifier), window_start=window_start
    )
    if queryset.update(count=F("count") + 1):
        return queryset.values_list("count", flat=True).get()
    try:
        with transaction.atomic():
            RateLimitCounter.objects.create(
                scope=scope,
                identifier=_hash(identifier),
                window_start=window_start,
                count=1,
            )
        return 1
    except IntegrityError:
        # 同時に別のリクエストが行を作成した場合は、その行へ加算する。
        queryset.update(count=F("count") + 1)
        return queryset.values_list("count", flat=True).get()


def hit(scope: str, identifier: str) -> bool:
    """呼び出しを 1 回数え、上限以内であれば True を返す。上限を超えた場合は False を返す。"""
    limit, window = settings.RATE_LIMITS[scope]
    window_start = int(time.time()) // window * window
    return increment(scope, identifier, window_start) <= limit


def retry_after(scope: str) -> int:
    """次の区間が始まるまでの秒数。"""
    _, window = settings.RATE_LIMITS[scope]
    return window - int(time.time()) % window


def purge_expired() -> int:
    """保持期間を過ぎた回数の行を削除し、削除した件数を返す。"""
    threshold = int(time.time()) - RETENTION_SECONDS
    deleted, _ = RateLimitCounter.objects.filter(window_start__lt=threshold).delete()
    return deleted
