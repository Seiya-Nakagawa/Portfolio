from django.db import migrations

SEPARATOR = "、"
OLD_NAME = "保守・運用"
NEW_NAME = "運用・保守"
# 統合後の担当工程の並び。統合した工程は選択肢の位置に揃える。
PHASE_ORDER = [
    "要件定義",
    "基本設計",
    "詳細設計",
    "実装",
    "単体テスト",
    "結合テスト",
    "総合テスト",
    NEW_NAME,
]


def merge_operation_phase(apps, schema_editor):
    """担当工程の「保守・運用」を「運用・保守」へ統合する。"""
    Project = apps.get_model("portfolio", "Project")
    for project in Project.objects.filter(phases__contains=OLD_NAME):
        phases = [NEW_NAME if p == OLD_NAME else p for p in project.phases.split(SEPARATOR) if p]
        unique = list(dict.fromkeys(phases))
        known = [p for p in PHASE_ORDER if p in unique]
        # 選択肢にない旧データの値は、選択肢の後ろに元の順で残す。
        others = [p for p in unique if p not in PHASE_ORDER]
        project.phases = SEPARATOR.join(known + others)
        project.save(update_fields=["phases"])


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0018_skill_is_master"),
    ]

    operations = [
        migrations.RunPython(merge_operation_phase, migrations.RunPython.noop),
    ]
