"""データの所有者（owner_id）を追加するための準備（基本設計書 4.15 の 1）。

各テーブルに空を許す owner_id を追加し、user_profiles・usage_daily を作成する。
site_info・skillsheet_texts は主キーを自動採番の識別子へ変更する。
既存の行への所有者の設定は 0022、必須化と一意性の変更は 0023 で行う。
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _owner(null: bool = True, **kwargs) -> models.ForeignKey:
    return models.ForeignKey(
        null=null,
        blank=null,
        on_delete=django.db.models.deletion.CASCADE,
        db_column="owner_id",
        related_name="+",
        to=settings.AUTH_USER_MODEL,
        verbose_name="所有者",
        **kwargs,
    )


def copy_skillsheet_texts(apps, schema_editor):
    """主キー変更前の文章項目を、新しい表へ写す（所有者は 0022 で設定する）。"""
    Old = apps.get_model("portfolio", "SkillsheetText")
    New = apps.get_model("portfolio", "SkillsheetTextNew")
    New.objects.bulk_create(
        New(text_key=t.text_key, body=t.body, updated_at=t.updated_at)
        for t in Old.objects.all()
    )


def restore_skillsheet_texts(apps, schema_editor):
    Old = apps.get_model("portfolio", "SkillsheetText")
    New = apps.get_model("portfolio", "SkillsheetTextNew")
    Old.objects.bulk_create(
        Old(text_key=t.text_key, body=t.body, updated_at=t.updated_at)
        for t in New.objects.all()
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portfolio", "0020_all_skills_master"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="profile",
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ユーザー",
                    ),
                ),
                ("is_public", models.BooleanField(default=False, verbose_name="公開する")),
                ("terms_version", models.CharField(blank=True, default="", max_length=32, verbose_name="同意した利用規約の版")),
                ("privacy_version", models.CharField(blank=True, default="", max_length=32, verbose_name="同意したプライバシーポリシーの版")),
                ("agreed_at", models.DateTimeField(blank=True, null=True, verbose_name="同意日時")),
            ],
            options={
                "verbose_name": "ユーザーのプロフィール",
                "verbose_name_plural": "ユーザーのプロフィール",
                "db_table": "user_profiles",
            },
        ),
        migrations.CreateModel(
            name="UsageDaily",
            fields=[
                ("pk", models.CompositePrimaryKey("usage_date", "metric", blank=True, editable=False, primary_key=True, serialize=False)),
                ("usage_date", models.DateField(verbose_name="集計日")),
                (
                    "metric",
                    models.CharField(
                        choices=[
                            ("signup", "サインアップ数"),
                            ("withdrawal", "退会数"),
                            ("skillsheet_pdf", "職務経歴書 PDF の生成回数"),
                            ("skillsheet_md", "職務経歴書 Markdown の生成回数"),
                        ],
                        max_length=32,
                        verbose_name="指標",
                    ),
                ),
                ("count", models.PositiveIntegerField(default=0, verbose_name="件数")),
            ],
            options={
                "verbose_name": "利用状況の日次集計",
                "verbose_name_plural": "利用状況の日次集計",
                "db_table": "usage_daily",
            },
        ),
        # ユーザーの削除時に所有する行をまとめて連鎖削除できるよう、保護から制限へ変更する。
        # 制限は、参照する行が同じ削除で一緒に削除される場合は削除を妨げない。
        migrations.AlterField(
            model_name="project",
            name="company",
            field=models.ForeignKey(
                blank=True,
                db_column="company_id",
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="projects",
                to="portfolio.company",
                verbose_name="会社",
            ),
        ),
        migrations.AlterField(
            model_name="projectskill",
            name="skill",
            field=models.ForeignKey(
                db_column="skill_id",
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="project_skills",
                to="portfolio.skill",
                verbose_name="スキル項目",
            ),
        ),
        # 共通マスタのスキル項目は所有者を持たない（空のまま）。
        migrations.AddField(model_name="skill", name="owner", field=_owner()),
        migrations.AddField(model_name="project", name="owner", field=_owner()),
        migrations.AddField(model_name="certification", name="owner", field=_owner()),
        migrations.AddField(model_name="work", name="owner", field=_owner()),
        migrations.AddField(model_name="company", name="owner", field=_owner()),
        # site_info: 固定値の主キーを自動採番へ変更し、ユーザーごとに 1 行にする。
        migrations.AlterField(
            model_name="siteinfo",
            name="site_info_id",
            field=models.AutoField(primary_key=True, serialize=False, verbose_name="サイト情報ID"),
        ),
        migrations.AddField(
            model_name="siteinfo",
            name="owner",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                db_column="owner_id",
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="所有者",
            ),
        ),
        # skillsheet_texts: 項目キーの主キーを自動採番の識別子へ変更する。
        # 主キーの付け替えは表を作り直して行う（既存の行は写す）。
        migrations.CreateModel(
            name="SkillsheetTextNew",
            fields=[
                ("skillsheet_text_id", models.AutoField(primary_key=True, serialize=False, verbose_name="文章項目ID")),
                ("owner", _owner()),
                ("text_key", models.CharField(max_length=32, verbose_name="項目キー")),
                ("body", models.TextField(verbose_name="内容")),
                ("updated_at", models.DateTimeField(verbose_name="最終更新日時")),
            ],
            options={
                "verbose_name": "職務経歴書の文章項目",
                "verbose_name_plural": "職務経歴書の文章項目",
                "db_table": "skillsheet_texts_new",
            },
        ),
        migrations.RunPython(copy_skillsheet_texts, restore_skillsheet_texts),
        migrations.DeleteModel(name="SkillsheetText"),
        migrations.AlterModelTable(name="SkillsheetTextNew", table="skillsheet_texts"),
        migrations.RenameModel(old_name="SkillsheetTextNew", new_name="SkillsheetText"),
        migrations.AddConstraint(
            model_name="skillsheettext",
            constraint=models.UniqueConstraint(fields=("owner", "text_key"), name="uniq_skillsheet_text_owner_key"),
        ),
    ]
