from django.db import migrations

MERGED_CATEGORY = "OS・MW"
OS_CATEGORY = "OS"
MIDDLEWARE_CATEGORY = "ミドルウェア"
# 統合前は OS だった項目の表示名。この一覧にない項目はミドルウェアへ振り分ける。
OS_SKILL_NAMES = {"Linux", "Windows"}
SORT_ORDER_STEP = 10


def split_categories(apps, schema_editor):
    """統合されていた「OS・MW」を「OS」と「ミドルウェア」の2種類に分離する。"""
    Skill = apps.get_model("portfolio", "Skill")
    SkillCategory = apps.get_model("portfolio", "SkillCategory")

    if not SkillCategory.objects.filter(name=MERGED_CATEGORY).exists():
        return

    order = list(
        SkillCategory.objects.order_by("sort_order", "id").values_list(
            "name", flat=True
        )
    )
    index = order.index(MERGED_CATEGORY)
    order[index : index + 1] = [OS_CATEGORY, MIDDLEWARE_CATEGORY]

    for skill in Skill.objects.filter(category=MERGED_CATEGORY):
        skill.category = (
            OS_CATEGORY if skill.name in OS_SKILL_NAMES else MIDDLEWARE_CATEGORY
        )
        skill.save(update_fields=["category"])

    SkillCategory.objects.filter(name=MERGED_CATEGORY).update(name=OS_CATEGORY)
    SkillCategory.objects.create(name=MIDDLEWARE_CATEGORY, sort_order=0)

    rank = {name: position for position, name in enumerate(order)}
    skills = list(Skill.objects.order_by("sort_order", "skill_id"))
    skills.sort(
        key=lambda s: (
            rank[s.category],
            s.subcategory == "",
            s.subcategory.casefold(),
            s.name.casefold(),
            s.skill_id,
        )
    )
    for position, skill in enumerate(skills, start=1):
        skill.sort_order = position * SORT_ORDER_STEP
    Skill.objects.bulk_update(skills, ["sort_order"])

    categories = {c.name: c for c in SkillCategory.objects.all()}
    for position, name in enumerate(order, start=1):
        categories[name].sort_order = position * SORT_ORDER_STEP
    SkillCategory.objects.bulk_update(categories.values(), ["sort_order"])


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0012_certification_ascending_order"),
    ]

    operations = [
        migrations.RunPython(split_categories, migrations.RunPython.noop),
    ]
