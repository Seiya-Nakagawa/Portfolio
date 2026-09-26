from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0003_site_info"),
    ]

    operations = [
        migrations.RemoveField(model_name="skill", name="level"),
        migrations.DeleteModel(name="Level"),
    ]
