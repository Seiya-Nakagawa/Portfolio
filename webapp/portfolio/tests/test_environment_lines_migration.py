from importlib import import_module

from django.apps import apps
from django.test import TestCase

from portfolio.models import Project

migration = import_module("portfolio.migrations.0017_environment_one_item_per_line")


class EnvironmentLinesMigrationTests(TestCase):
    def test_読点区切りを1行1項目に変換する(self):
        Project.objects.create(
            name="A", start_year_month="2025-01", environment="AWS、Python 3.14、"
        )
        Project.objects.create(name="B", start_year_month="2025-02")

        migration.split_environment(apps, None)

        self.assertEqual(
            dict(Project.objects.values_list("name", "environment")),
            {"A": "AWS\nPython 3.14", "B": ""},
        )

    def test_元に戻すと読点区切りになる(self):
        Project.objects.create(
            name="A", start_year_month="2025-01", environment="AWS\nPython 3.14"
        )

        migration.join_environment(apps, None)

        self.assertEqual(Project.objects.get().environment, "AWS、Python 3.14")
