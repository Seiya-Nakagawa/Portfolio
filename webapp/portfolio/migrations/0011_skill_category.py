from django.db import migrations, models

MERGED_CATEGORY = "OS・MW"
MERGED_SOURCES = ("OS", "ミドルウェア")
SORT_ORDER_STEP = 10


def create_categories(apps, schema_editor):
    """OS とミドルウェアを「OS・MW」へ統合し、種類マスタを既存のスキル項目から作成する。"""
    Skill = apps.get_model("portfolio", "Skill")
    SkillCategory = apps.get_model("portfolio", "SkillCategory")
    Skill.objects.filter(category__in=MERGED_SOURCES).update(category=MERGED_CATEGORY)

    skills = list(Skill.objects.order_by("sort_order", "skill_id"))
    rank: dict[str, int] = {}
    for skill in skills:
        rank.setdefault(skill.category, len(rank))
    # 統合した種類は、統合前の先頭の位置にまとめて並べる。
    skills.sort(
        key=lambda s: (
            rank[s.category],
            s.subcategory == "",
            s.subcategory.casefold(),
            s.name.casefold(),
            s.skill_id,
        )
    )
    for index, skill in enumerate(skills, start=1):
        skill.sort_order = index * SORT_ORDER_STEP
    Skill.objects.bulk_update(skills, ["sort_order"])
    SkillCategory.objects.bulk_create(
        SkillCategory(name=name, sort_order=(index + 1) * SORT_ORDER_STEP)
        for name, index in rank.items()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0010_year_month_dates"),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64, unique=True, verbose_name="種類名")),
                ("sort_order", models.PositiveIntegerField(verbose_name="表示順")),
            ],
            options={
                "verbose_name": "スキル項目の種類",
                "verbose_name_plural": "スキル項目の種類",
                "db_table": "skill_categories",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.RunPython(create_categories, migrations.RunPython.noop),
    ]
