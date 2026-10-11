from importlib import import_module

from django.apps import apps
from django.test import TestCase

from portfolio.models import Project

migration = import_module("portfolio.migrations.0019_merge_operation_phase")


class MergeOperationPhaseMigrationTests(TestCase):
    def _phases(self, name):
        return Project.objects.get(name=name).phases

    def test_保守運用を運用保守へ統合する(self):
        Project.objects.create(
            name="A", start_year_month="2025-01", phases="基本設計、保守・運用"
        )
        Project.objects.create(
            name="B", start_year_month="2025-01", phases="保守・運用"
        )

        migration.merge_operation_phase(apps, None)

        self.assertEqual(self._phases("A"), "基本設計、運用・保守")
        self.assertEqual(self._phases("B"), "運用・保守")

    def test_両方ある場合は1つにまとめ_選択肢の順に並べる(self):
        Project.objects.create(
            name="A",
            start_year_month="2025-01",
            phases="運用・保守、製造、保守・運用、詳細設計",
        )

        migration.merge_operation_phase(apps, None)

        self.assertEqual(self._phases("A"), "詳細設計、運用・保守、製造")

    def test_対象外の案件は変更しない(self):
        Project.objects.create(
            name="A", start_year_month="2025-01", phases="運用・保守、基本設計"
        )
        Project.objects.create(name="B", start_year_month="2025-01")

        migration.merge_operation_phase(apps, None)

        self.assertEqual(self._phases("A"), "運用・保守、基本設計")
        self.assertEqual(self._phases("B"), "")
