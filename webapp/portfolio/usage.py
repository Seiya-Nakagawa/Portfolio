"""利用状況の日次集計値（`usage_daily`）の加算。ユーザーを特定できる情報は記録しない。"""

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from portfolio.models import UsageDaily


def increment(metric: str, amount: int = 1) -> None:
    """当日の指標の件数を加算する。当日の行がなければ作成する。"""
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
