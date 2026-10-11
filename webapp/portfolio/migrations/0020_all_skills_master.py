from django.db import migrations


def mark_all_master(apps, schema_editor):
    """登録済みのスキル項目をすべてマスタ項目にする。"""
    Skill = apps.get_model("portfolio", "Skill")
    Skill.objects.update(is_master=True)


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0019_merge_operation_phase"),
    ]

    operations = [
        migrations.RunPython(mark_all_master, migrations.RunPython.noop),
    ]
