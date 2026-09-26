import importlib

from django.test import SimpleTestCase

migration = importlib.import_module("portfolio.migrations.0006_aws_subcategory_data")


class AwsSubcategoryLookupTests(SimpleTestCase):
    def setUp(self):
        self.lookup = migration.build_lookup()

    def _category(self, name):
        return self.lookup.get(migration.normalize(name))

    def test_接頭辞や表記ゆれを吸収して対応づける(self):
        self.assertEqual(self._category("Amazon EC2"), "Compute")
        self.assertEqual(self._category("AWS Lambda"), "Compute")
        self.assertEqual(self._category("Route 53"), "Networking & Content Delivery")
        self.assertEqual(self._category("route53"), "Networking & Content Delivery")

    def test_コンテナ系はContainersを優先する(self):
        self.assertEqual(self._category("ECS"), "Containers")
        self.assertEqual(self._category("EKS"), "Containers")

    def test_未知のサービスは対応しない(self):
        self.assertIsNone(self._category("Unknown Service"))
