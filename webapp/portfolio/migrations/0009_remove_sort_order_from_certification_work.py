from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0008_move_container_skills_and_resequence"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="certification",
            options={
                "ordering": ["-certification_id"],
                "verbose_name": "資格",
                "verbose_name_plural": "資格",
            },
        ),
        migrations.AlterModelOptions(
            name="work",
            options={
                "ordering": ["-work_id"],
                "verbose_name": "実績",
                "verbose_name_plural": "実績",
            },
        ),
        migrations.RemoveField(model_name="certification", name="sort_order"),
        migrations.RemoveField(model_name="work", name="sort_order"),
    ]
