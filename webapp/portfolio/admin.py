"""運営管理（Django の管理サイト）。運営者（`is_staff`）のみが利用できる。

利用状況の確認と、ユーザーの利用停止・再開に限り、案件・会社・職務経歴書データは表示しない。
管理サイトの独自のログイン画面は用いず、未ログインの場合は本サービスのログイン画面へ誘導する。
"""

from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from portfolio.models import UsageDaily

# 日次推移として表示する日数。
USAGE_DAYS = 30


class OperatorAdminSite(admin.AdminSite):
    site_header = "運営管理"
    site_title = "運営管理"
    index_title = "利用状況"
    index_template = "admin/usage_index.html"

    def has_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def index(self, request, extra_context=None):
        context = {**self._usage_summary(), **(extra_context or {})}
        return super().index(request, context)

    @staticmethod
    def _usage_summary() -> dict:
        """登録ユーザー数等は表示時にユーザー・プロフィールから数え、日次推移は `usage_daily` から作る。"""
        users = get_user_model().objects.aggregate(
            total=Count("pk"),
            suspended=Count("pk", filter=Q(is_active=False)),
            public=Count("pk", filter=Q(is_active=True, profile__is_public=True)),
        )
        today = timezone.localdate()
        days = [today - timedelta(days=offset) for offset in range(USAGE_DAYS)]
        counts = {
            (row.usage_date, row.metric): row.count
            for row in UsageDaily.objects.filter(usage_date__gte=days[-1])
        }
        metrics = UsageDaily.METRIC_CHOICES
        return {
            "user_counts": users,
            "usage_metrics": [label for _, label in metrics],
            "usage_rows": [
                {
                    "date": day,
                    "values": [counts.get((day, key), 0) for key, _ in metrics],
                }
                for day in days
            ],
        }


class OperatorOnlyAdmin(admin.ModelAdmin):
    """運営者のみが閲覧でき、追加・削除はできない。権限は `is_staff` で判定する。"""

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class UserAdmin(OperatorOnlyAdmin):
    """ユーザーの一覧と、利用停止・再開。

    ユーザーの作成・削除・ユーザー名の変更は行わない（ユーザー自身の操作に限る）。
    案件・会社・職務経歴書データは表示しない。
    """

    list_display = (
        "username",
        "email",
        "date_joined",
        "last_login",
        "is_public",
        "is_active",
    )
    list_display_links = None
    list_filter = ("is_active",)
    search_fields = ("username", "email")
    ordering = ("-date_joined",)
    actions = ("suspend", "resume")
    list_select_related = ("profile",)

    @admin.display(description="公開設定", boolean=True)
    def is_public(self, user) -> bool:
        profile = getattr(user, "profile", None)
        return bool(profile and profile.is_public)

    def get_actions(self, request):
        # 一括削除は提供しない。
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="選択したユーザーの利用を停止する")
    def suspend(self, request, queryset):
        # 自分自身を停止すると運営管理に入れなくなるため対象外とする。
        targets = queryset.exclude(pk=request.user.pk)
        if targets.count() != queryset.count():
            self.message_user(request, "自分自身は停止できません。", messages.WARNING)
        updated = targets.update(is_active=False)
        self.message_user(request, f"{updated} 件のユーザーの利用を停止しました。")

    @admin.action(description="選択したユーザーの利用を再開する")
    def resume(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} 件のユーザーの利用を再開しました。")


# 新しい管理サイトには何も自動登録されないため、ユーザーのみを登録する。
admin.site.register(get_user_model(), UserAdmin)
