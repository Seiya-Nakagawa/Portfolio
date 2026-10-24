"""利用状況の日次集計値（`usage_daily`）の加算。ユーザーを特定できる情報は記録しない。"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from portfolio.models import UsageDaily

logger = logging.getLogger(__name__)


def increment(metric: str, amount: int = 1) -> None:
    """当日の指標の件数を加算する。当日の行がなければ作成する。

    集計は付随的な記録であり、失敗しても呼び出し元の操作を妨げない。加算はセーブポイントの
    内側で行うため、呼び出し元のトランザクションも巻き込まない。
    """
    try:
        with transaction.atomic():
            _increment(metric, amount)
    except Exception as error:  # noqa: BLE001 - 失敗の原因を問わず元の操作を優先する
        logger.warning(
            "利用状況の加算に失敗しました。metric=%s error=%s",
            metric,
            type(error).__name__,
        )


def _increment(metric: str, amount: int) -> None:
    today = timezone.localdate()
    queryset = UsageDaily.objects.filter(usage_date=today, metric=metric)
    if queryset.update(count=F("count") + amount):
        return
    try:
        with transaction.atomic():
            UsageDaily.objects.create(usage_date=today, metric=metric, count=amount)
    except IntegrityError:
        # 同時に別のリクエストが行を作成した場合は、その行へ加算する。
        queryset.update(count=F("count") + amount)
