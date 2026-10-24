"""死活監視。実績 DB の読み取りと、日次の整理処理の最終成功時刻をヘルスチェックの判定に用いる。"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from portfolio.models import JobRun


def record_job_success(job_name: str) -> None:
    """定期ジョブの最終成功時刻を現在時刻に更新する。"""
    JobRun.objects.update_or_create(
        job_name=job_name, defaults={"succeeded_at": timezone.now()}
    )


def database_is_available() -> bool:
    """実績 DB に接続でき、主要なテーブルを読み取れるか。"""
    try:
        get_user_model().objects.values_list("pk", flat=True).first()
        return True
    except Exception:  # noqa: BLE001 - 接続できない原因を問わず異常とする
        return False


def daily_maintenance_is_recent() -> bool:
    """日次の整理処理が、許容時間内に成功しているか。記録がない場合は異常とする。"""
    try:
        succeeded_at = (
            JobRun.objects.filter(job_name=JobRun.JOB_DAILY_MAINTENANCE)
            .values_list("succeeded_at", flat=True)
            .first()
        )
    except Exception:  # noqa: BLE001 - 読み取れない原因（マイグレーション前を含む）を問わず異常とする
        return False
    if succeeded_at is None:
        return False
    limit = timedelta(hours=settings.HEALTH_MAINTENANCE_MAX_AGE_HOURS)
    return timezone.now() - succeeded_at <= limit


def is_healthy() -> bool:
    """実績 DB を読み取れ、日次の整理処理が許容時間内に成功していれば正常とする。

    サーバーエラー（5xx）の件数は判定に用いない。外部から 5xx を誘発して異常にできてしまうため。
    """
    return database_is_available() and daily_maintenance_is_recent()
