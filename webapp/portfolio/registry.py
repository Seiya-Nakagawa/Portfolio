"""登録画面の書き込み処理。入力値の検証はここで行い、画面側の入力制限に依存しない。

書き込みはトランザクション内で対象行をロックし、複数タブからの同時操作による不整合を防ぐ。
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from portfolio.models import (
    YEAR_MONTH_VALIDATOR,
    Certification,
    Level,
    Project,
    ProjectSkill,
    Skill,
    Work,
)

MAX_PROJECT_NAME_LENGTH = 255
MAX_VERSION_LENGTH = 64


class ValidationFailed(Exception):
    """入力値の検証エラー。画面へ返すメッセージの一覧を保持する。"""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class NotFound(Exception):
    """更新・削除の対象が存在しない。"""


def _validate_year_month(value: str, label: str, errors: list[str]) -> None:
    try:
        YEAR_MONTH_VALIDATOR(value)
    except ValidationError:
        errors.append(f"{label}は YYYY-MM 形式で入力してください。")


def _clean_project_payload(payload: dict) -> tuple[dict, list[dict]]:
    errors: list[str] = []

    name = str(payload.get("name") or "").strip()
    start = str(payload.get("start_year_month") or "").strip()
    end = str(payload.get("end_year_month") or "").strip()

    if not name:
        errors.append("案件名を入力してください。")
    elif len(name) > MAX_PROJECT_NAME_LENGTH:
        errors.append(f"案件名は{MAX_PROJECT_NAME_LENGTH}文字以内で入力してください。")

    if not start:
        errors.append("開始年月を入力してください。")
    else:
        _validate_year_month(start, "開始年月", errors)
    if end:
        _validate_year_month(end, "終了年月", errors)

    # YYYY-MM は文字列比較で年月の前後関係と一致する。形式エラーがない場合のみ比較する。
    if not errors and end and end < start:
        errors.append("終了年月は開始年月以降にしてください。")

    raw_skills = payload.get("skills") or []
    if not isinstance(raw_skills, list):
        errors.append("スキル項目の形式が不正です。")
        raw_skills = []

    skills: list[dict] = []
    seen: set[str] = set()
    for item in raw_skills:
        skill_id = str(item.get("skill_id") or "") if isinstance(item, dict) else ""
        version = (
            str(item.get("version") or "").strip() if isinstance(item, dict) else ""
        )
        if not skill_id:
            errors.append("スキル項目の形式が不正です。")
        elif skill_id in seen:
            errors.append(f"スキル項目が重複しています: {skill_id}")
        elif len(version) > MAX_VERSION_LENGTH:
            errors.append(
                f"バージョンは{MAX_VERSION_LENGTH}文字以内で入力してください: {skill_id}"
            )
        else:
            seen.add(skill_id)
            skills.append({"skill_id": skill_id, "version": version})

    existing = set(
        Skill.objects.filter(skill_id__in=seen).values_list("skill_id", flat=True)
    )
    for skill_id in sorted(seen - existing):
        errors.append(f"存在しないスキル項目です: {skill_id}")

    if errors:
        raise ValidationFailed(errors)
    return {"name": name, "start_year_month": start, "end_year_month": end}, skills


def save_project(payload: dict) -> Project:
    """案件と使用スキルを保存する。既存の使用スキルは削除して置き換える。"""
    fields, skills = _clean_project_payload(payload)
    project_id = payload.get("project_id")

    with transaction.atomic():
        if project_id:
            try:
                project = Project.objects.select_for_update().get(pk=project_id)
            except Project.DoesNotExist:
                raise NotFound("案件が見つかりません。") from None
            for key, value in fields.items():
                setattr(project, key, value)
            project.save()
            ProjectSkill.objects.filter(project=project).delete()
        else:
            project = Project.objects.create(**fields)

        ProjectSkill.objects.bulk_create(
            ProjectSkill(
                project=project, skill_id=item["skill_id"], version=item["version"]
            )
            for item in skills
        )
    return project


def delete_project(project_id: str) -> None:
    """案件を削除する。紐づく使用スキルも同時に削除される。"""
    with transaction.atomic():
        try:
            project = Project.objects.select_for_update().get(pk=project_id)
        except Project.DoesNotExist:
            raise NotFound("案件が見つかりません。") from None
        project.delete()


def _to_int(value, label: str) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        raise ValidationFailed([f"{label}は整数で入力してください。"]) from None


def _save_model(instance) -> None:
    try:
        instance.full_clean()
    except ValidationError as error:
        labels = {f.name: f.verbose_name for f in instance._meta.fields}
        messages = []
        for field, field_errors in error.message_dict.items():
            label = labels.get(field, "")
            messages.extend(f"{label}: {m}" if label else m for m in field_errors)
        raise ValidationFailed(messages) from None
    instance.save()


def _apply(instance, payload: dict, text_fields: list[str]) -> None:
    for name in text_fields:
        setattr(instance, name, str(payload.get(name) or "").strip())
    instance.sort_order = _to_int(payload.get("sort_order"), "表示順")


def save_skill(payload: dict, skill_id: str | None = None) -> Skill:
    """スキル項目を追加（skill_id 未指定）または変更する。skill_id は変更できない。"""
    with transaction.atomic():
        if skill_id is None:
            new_id = str(payload.get("skill_id") or "").strip()
            if Skill.objects.filter(pk=new_id).exists():
                raise ValidationFailed([f"skill_id は既に登録されています: {new_id}"])
            skill = Skill(skill_id=new_id)
        else:
            try:
                skill = Skill.objects.select_for_update().get(pk=skill_id)
            except Skill.DoesNotExist:
                raise NotFound("スキル項目が見つかりません。") from None

        _apply(skill, payload, ["category", "name", "remarks"])
        level = _to_int(payload.get("level"), "レベル")
        if not Level.objects.filter(pk=level).exists():
            raise ValidationFailed([f"存在しないレベルです: {level}"])
        skill.level_id = level
        _save_model(skill)
    return skill


def delete_skill(skill_id: str) -> None:
    """使用実績が紐づかないスキル項目のみ削除できる。"""
    with transaction.atomic():
        try:
            skill = Skill.objects.select_for_update().get(pk=skill_id)
        except Skill.DoesNotExist:
            raise NotFound("スキル項目が見つかりません。") from None
        if skill.project_skills.exists():
            raise ValidationFailed(["使用実績が紐づくスキル項目は削除できません。"])
        skill.delete()


def save_certification(
    payload: dict, certification_id: int | None = None
) -> Certification:
    with transaction.atomic():
        if certification_id is None:
            certification = Certification()
        else:
            try:
                certification = Certification.objects.select_for_update().get(
                    pk=certification_id
                )
            except Certification.DoesNotExist:
                raise NotFound("資格が見つかりません。") from None
        _apply(certification, payload, ["name", "acquired_on", "org"])
        _save_model(certification)
    return certification


def delete_certification(certification_id: int) -> None:
    with transaction.atomic():
        deleted, _ = Certification.objects.filter(pk=certification_id).delete()
        if not deleted:
            raise NotFound("資格が見つかりません。")


def _clean_tags(value) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
        raise ValidationFailed(["使用技術タグは文字列の一覧で指定してください。"])
    return [t.strip() for t in value if t.strip()]


def save_work(payload: dict, work_id: int | None = None) -> Work:
    with transaction.atomic():
        if work_id is None:
            work = Work()
        else:
            try:
                work = Work.objects.select_for_update().get(pk=work_id)
            except Work.DoesNotExist:
                raise NotFound("実績が見つかりません。") from None
        _apply(
            work,
            payload,
            ["title", "desc_ja", "desc_en", "thumbnail", "github_url", "live_url"],
        )
        work.tags = _clean_tags(payload.get("tags"))
        _save_model(work)
    return work


def delete_work(work_id: int) -> None:
    with transaction.atomic():
        deleted, _ = Work.objects.filter(pk=work_id).delete()
        if not deleted:
            raise NotFound("実績が見つかりません。")
