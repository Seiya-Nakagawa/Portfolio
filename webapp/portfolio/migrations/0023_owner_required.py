"""所有者を必須にする（基本設計書 4.15 の 4）。

共通マスタを持つ skills を除く各テーブルの owner_id を必須にする。
site_info・skillsheet_texts の所有者単位の一意性は 0021 で定義済み。
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _required(field_class=models.ForeignKey) -> models.Field:
    return field_class(
        on_delete=django.db.models.deletion.CASCADE,
        db_column="owner_id",
        related_name="+",
        to=settings.AUTH_USER_MODEL,
        verbose_name="所有者",
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portfolio", "0022_assign_owner"),
    ]

    operations = [
        migrations.AlterField(model_name=name, name="owner", field=_required())
        for name in ("project", "certification", "work", "company", "skillsheettext")
    ]
    operations.append(
        migrations.AlterField(
            model_name="siteinfo", name="owner", field=_required(models.OneToOneField)
        )
    )
