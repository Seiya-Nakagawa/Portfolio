"""既存データを運営者に紐づける（基本設計書 4.15 の 2・3）。

単一ユーザー構成で蓄積した行の owner_id に、既存の唯一のユーザー（運営者）を設定する。
ユーザーが 1 人でない場合は移行を中止する。スキル項目は共通マスタとして所有者を空のままにする。
"""

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations

# 所有者を設定する（共通マスタを持たない）モデル。
OWNED_MODELS = ["Project", "Certification", "Work", "SiteInfo", "Company", "SkillsheetText"]


def assign_owner(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    UserProfile = apps.get_model("portfolio", "UserProfile")

    users = list(User.objects.all()[:2])
    has_rows = any(apps.get_model("portfolio", name).objects.exists() for name in OWNED_MODELS)
    if not users and not has_rows:
        # 新規構築: 移行するデータがない。
        return
    if len(users) != 1:
        raise RuntimeError(
            "既存データの移行には、運営者のユーザーがちょうど 1 人必要です。"
            f"現在のユーザー数: {'2 人以上' if users else '0 人'}。"
            "ユーザーを整えてからマイグレーションを再実行してください。"
        )

    operator = users[0]
    for name in OWNED_MODELS:
        apps.get_model("portfolio", name).objects.filter(owner__isnull=True).update(owner=operator)

    # 運営者のアカウントを整える。パスワードでログインできない状態（使用不可の値）にする。
    operator.is_staff = True
    operator.password = make_password(None)
    operator.save(update_fields=["is_staff", "password"])
    UserProfile.objects.get_or_create(user=operator, defaults={"is_public": True})


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portfolio", "0021_owner_columns"),
    ]

    operations = [
        migrations.RunPython(assign_owner, migrations.RunPython.noop),
    ]
