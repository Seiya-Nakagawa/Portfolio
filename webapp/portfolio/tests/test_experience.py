from datetime import date

from django.test import SimpleTestCase

from portfolio.experience import (
    ProjectPeriod,
    SkillUsage,
    aggregate_skill_experience,
    expand_months,
    format_experience,
    to_month_index,
)

TODAY = date(2026, 9, 25)


class ExpandMonthsTests(SimpleTestCase):
    def test_開始と終了を含む月数に展開する(self):
        self.assertEqual(len(expand_months("2024-01", "2024-03", TODAY)), 3)

    def test_年をまたいで展開する(self):
        months = expand_months("2023-11", "2024-02", TODAY)
        self.assertEqual(
            months,
            {to_month_index(m) for m in ("2023-11", "2023-12", "2024-01", "2024-02")},
        )

    def test_終了年月が空なら基準日の月まで展開する(self):
        self.assertEqual(len(expand_months("2026-07", "", TODAY)), 3)

    def test_開始が終了より後なら空になる(self):
        self.assertEqual(expand_months("2024-05", "2024-03", TODAY), set())


class FormatExperienceTests(SimpleTestCase):
    def test_0ヶ月は出力対象外(self):
        self.assertIsNone(format_experience(0))

    def test_12ヶ月未満はMヶ月(self):
        self.assertEqual(format_experience(7), "7ヶ月")
        self.assertEqual(format_experience(11), "11ヶ月")

    def test_12ヶ月ちょうどはN年(self):
        self.assertEqual(format_experience(12), "1年")
        self.assertEqual(format_experience(48), "4年")

    def test_剰余ありはN年Mヶ月(self):
        self.assertEqual(format_experience(58), "4年10ヶ月")
        self.assertEqual(format_experience(13), "1年1ヶ月")


class AggregateSkillExperienceTests(SimpleTestCase):
    def test_重複する年月は1ヶ月として数える(self):
        projects = [
            ProjectPeriod("a", "2024-01", "2024-06"),
            ProjectPeriod("b", "2024-04", "2024-09"),
        ]
        usages = [SkillUsage("a", "python"), SkillUsage("b", "python")]

        result = aggregate_skill_experience(projects, usages, TODAY)

        # 2024-01〜2024-09 の 9 ヶ月（4〜6 月の重複は 1 回のみ）
        self.assertEqual(result["python"].months, 9)

    def test_離れた期間は合算する(self):
        projects = [
            ProjectPeriod("a", "2022-01", "2022-03"),
            ProjectPeriod("b", "2024-01", "2024-02"),
        ]
        usages = [SkillUsage("a", "aws"), SkillUsage("b", "aws")]

        result = aggregate_skill_experience(projects, usages, TODAY)

        self.assertEqual(result["aws"].months, 5)

    def test_継続中の案件は基準日まで数える(self):
        projects = [ProjectPeriod("a", "2026-08", "")]

        result = aggregate_skill_experience(projects, [SkillUsage("a", "k8s")], TODAY)

        self.assertEqual(result["k8s"].months, 2)

    def test_開始年は紐づく案件の最小開始年(self):
        projects = [
            ProjectPeriod("a", "2024-05", "2024-06"),
            ProjectPeriod("b", "2021-03", "2021-04"),
        ]
        usages = [SkillUsage("a", "linux"), SkillUsage("b", "linux")]

        result = aggregate_skill_experience(projects, usages, TODAY)

        self.assertEqual(result["linux"].start_year, 2021)

    def test_使用実績のないスキルは含まれない(self):
        projects = [ProjectPeriod("a", "2024-01", "2024-02")]

        result = aggregate_skill_experience(projects, [SkillUsage("a", "go")], TODAY)

        self.assertEqual(set(result), {"go"})
        self.assertNotIn("rust", result)

    def test_存在しない案件への実績は無視する(self):
        result = aggregate_skill_experience([], [SkillUsage("zzz", "go")], TODAY)

        self.assertEqual(result, {})

    def test_ジェネレータを渡しても集計できる(self):
        projects = (p for p in [ProjectPeriod("a", "2024-01", "2024-02")])
        usages = (u for u in [SkillUsage("a", "go")])

        result = aggregate_skill_experience(projects, usages, TODAY)

        self.assertEqual(result["go"].months, 2)
