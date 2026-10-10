"""登録画面（本人のログインが必要）のページと JSON API。"""

import json
from collections import Counter
from functools import wraps
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from portfolio import export, registry, uploads
from portfolio.models import (
    PROJECT_PHASES,
    SKILLSHEET_TEXT_KEYS,
    Certification,
    Company,
    Project,
    SiteInfo,
    Skill,
    SkillsheetText,
    Work,
)
from portfolio.services import (
    build_skill_rows,
    ordered_certifications,
    ordered_skills,
    ordered_works,
)


def _json(data, status: int = 200) -> JsonResponse:
    return JsonResponse(
        data, status=status, safe=False, json_dumps_params={"ensure_ascii": False}
    )


def api_view(*methods: str):
    """ログイン必須・メソッド制限・エラー応答の共通処理を行う API ビューのデコレータ。"""

    def decorator(view):
        @wraps(view)
        @require_http_methods(list(methods))
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return _json({"errors": ["ログインが必要です。"]}, status=401)
            try:
                return view(request, *args, **kwargs)
            except registry.ValidationFailed as error:
                return _json({"errors": error.errors}, status=400)
            except registry.NotFound as error:
                return _json({"errors": [str(error)]}, status=404)

        return wrapper

    return decorator


def _body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise registry.ValidationFailed(["リクエストの形式が不正です。"]) from None
    if not isinstance(body, dict):
        raise registry.ValidationFailed(["リクエストの形式が不正です。"])
    return body


def _skill_dict(skill: Skill, years: str = "") -> dict:
    return {
        "skill_id": skill.skill_id,
        "category": skill.category,
        "subcategory": skill.subcategory,
        "name": skill.name,
        "is_master": skill.is_master,
        "years": years,
    }


def _project_dict(project: Project) -> dict:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "start_year_month": project.start_year_month,
        "end_year_month": project.end_year_month,
        "company_id": project.company_id,
        "team_size": project.team_size,
        "overview": project.overview,
        "tasks": project.tasks,
        "phases": registry.split_phases(project.phases),
        "environment": project.environment,
        "skills": [
            {"skill_id": ps.skill_id, "version": ps.version}
            for ps in project.project_skills.order_by("skill_id")
        ],
    }


COMPANY_FIELDS = [
    "company_id",
    "name",
    "department",
    "employment_type",
    "kind",
    "start_year_month",
    "end_year_month",
    "capital",
    "employees",
    "offices",
    "annual_sales",
    "founded",
]


def _company_dict(company: Company, project_count: int) -> dict:
    return {
        **{name: getattr(company, name) for name in COMPANY_FIELDS},
        "project_count": project_count,
    }


def _companies() -> list[dict]:
    counts = Counter(
        Project.objects.exclude(company=None).values_list("company_id", flat=True)
    )
    return [
        _company_dict(c, counts.get(c.company_id, 0)) for c in Company.objects.all()
    ]


def _certification_dict(c: Certification) -> dict:
    return {
        "certification_id": c.certification_id,
        "name": c.name,
        "acquired_on": c.acquired_on.strftime("%Y-%m"),
        "org": c.org,
    }


def _work_dict(w: Work) -> dict:
    return {
        "work_id": w.work_id,
        "title": w.title,
        "achieved_on": w.achieved_on.strftime("%Y-%m") if w.achieved_on else "",
        "desc_ja": w.desc_ja,
        "desc_en": w.desc_en,
        "tags": w.tags,
        "thumbnail": w.thumbnail,
        "github_url": w.github_url,
        "live_url": w.live_url,
    }


def _ongoing_projects():
    """継続中（終了年月が未設定）の案件を、開始年月の降順で返す。"""
    return Project.objects.filter(end_year_month="").order_by(
        "-start_year_month", "project_id"
    )


def _finished_projects():
    """終了済み（終了年月が設定済み）の案件を、終了年月・開始年月の降順で返す。"""
    return Project.objects.exclude(end_year_month="").order_by(
        "-end_year_month", "-start_year_month", "project_id"
    )


def _skills_with_years() -> list[dict]:
    years_by_skill = {
        row.skill.skill_id: row.years for row in build_skill_rows(timezone.localdate())
    }
    return [
        _skill_dict(s, years_by_skill.get(s.skill_id, "")) for s in ordered_skills()
    ]


@login_required
@ensure_csrf_cookie
@require_http_methods(["GET"])
def index(request):
    return render(request, "manage/index.html")


@api_view("GET")
def api_bootstrap(request):
    """案件登録の初期表示データ。"""
    ongoing = list(_ongoing_projects())
    return _json(
        {
            "skills": _skills_with_years(),
            "categories": registry.category_names(),
            "companies": _companies(),
            "phases": PROJECT_PHASES,
            "ongoing_projects": [
                {"project_id": p.project_id, "name": p.name} for p in ongoing
            ],
            "finished_projects": [
                {
                    "project_id": p.project_id,
                    "name": p.name,
                    "start_year_month": p.start_year_month,
                    "end_year_month": p.end_year_month,
                }
                for p in _finished_projects()
            ],
            "initial_project": _project_dict(ongoing[0]) if ongoing else None,
        }
    )


@api_view("GET", "DELETE")
def api_project(request, project_id):
    if request.method == "DELETE":
        registry.delete_project(project_id)
        return _json({"ok": True})
    try:
        return _json(_project_dict(Project.objects.get(pk=project_id)))
    except Project.DoesNotExist:
        raise registry.NotFound("案件が見つかりません。") from None


@api_view("POST")
def api_projects(request):
    project = registry.save_project(_body(request))
    return _json(_project_dict(project))


@api_view("GET", "POST")
def api_skills(request):
    if request.method == "POST":
        registry.save_skill(_body(request))
    return _json(_skills_with_years())


def _categories() -> list[dict]:
    counts = Counter(Skill.objects.values_list("category", flat=True))
    return [
        {"name": name, "skill_count": counts.get(name, 0)}
        for name in registry.category_names()
    ]


@api_view("GET", "POST")
def api_categories(request):
    if request.method == "POST":
        registry.add_skill_category(_body(request))
    return _json(_categories())


@api_view("POST")
def api_category_order(request):
    """種類単位の並び順を保存する。"""
    registry.reorder_skill_categories(_body(request))
    return _json(_categories())


@api_view("PUT", "DELETE")
def api_category(request, category_name):
    if request.method == "DELETE":
        registry.delete_skill_category(category_name)
    else:
        registry.rename_skill_category(category_name, _body(request))
    return _json(_categories())


@api_view("PUT", "DELETE")
def api_skill(request, skill_id):
    if request.method == "DELETE":
        registry.delete_skill(skill_id)
    else:
        registry.save_skill(_body(request), skill_id)
    return _json(_skills_with_years())


def _certifications() -> list[dict]:
    return [_certification_dict(c) for c in ordered_certifications()]


@api_view("GET", "POST")
def api_certifications(request):
    if request.method == "POST":
        registry.save_certification(_body(request))
    return _json(_certifications())


@api_view("PUT", "DELETE")
def api_certification(request, certification_id):
    if request.method == "DELETE":
        registry.delete_certification(certification_id)
    else:
        registry.save_certification(_body(request), certification_id)
    return _json(_certifications())


def _works() -> list[dict]:
    return [_work_dict(w) for w in ordered_works()]


@api_view("GET", "POST")
def api_works(request):
    if request.method == "POST":
        registry.save_work(_body(request))
    return _json(_works())


@api_view("PUT", "DELETE")
def api_work(request, work_id):
    if request.method == "DELETE":
        registry.delete_work(work_id)
    else:
        registry.save_work(_body(request), work_id)
    return _json(_works())


SITE_INFO_FIELDS = [
    *registry.SITE_INFO_TEXT_FIELDS,
    "typing_titles",
    "birth_date",
    "copyright_start_year",
]


def _site_info() -> dict:
    """管理画面向けのサイト情報。未登録の場合は空のフォームを表示するため空の値を返す。"""
    info = SiteInfo.objects.first()
    if info is None:
        return {name: "" for name in SITE_INFO_FIELDS} | {"typing_titles": []}
    data = {name: getattr(info, name) for name in SITE_INFO_FIELDS}
    data["birth_date"] = info.birth_date.isoformat()
    return data


@api_view("GET", "PUT")
def api_site(request):
    if request.method == "PUT":
        registry.save_site_info(_body(request))
    return _json(_site_info())


@api_view("GET", "POST")
def api_companies(request):
    if request.method == "POST":
        registry.save_company(_body(request))
    return _json(_companies())


@api_view("PUT", "DELETE")
def api_company(request, company_id):
    if request.method == "DELETE":
        registry.delete_company(company_id)
    else:
        registry.save_company(_body(request), company_id)
    return _json(_companies())


def _skillsheet_payload() -> dict:
    """職務経歴書画面向けのデータ。文章項目・プレビュー・警告を返す。"""
    saved = {t.text_key: t for t in SkillsheetText.objects.all()}
    texts = [
        {
            "key": key,
            "label": label,
            "body": saved[key].body if key in saved else "",
            "updated_at": saved[key].updated_at.isoformat() if key in saved else None,
        }
        for key, label in SKILLSHEET_TEXT_KEYS.items()
    ]
    rendered = export.render_skillsheet(timezone.localdate())
    return {
        "texts": texts,
        "preview_html": rendered.html,
        "warnings": rendered.warnings.as_dict(),
    }


@api_view("GET")
def api_skillsheet(request):
    return _json(_skillsheet_payload())


@api_view("PUT")
def api_skillsheet_text(request, text_key):
    data = _body(request)
    registry.save_skillsheet_text(
        text_key, data.get("body"), data.get("expected_updated_at")
    )
    return _json(_skillsheet_payload())


def _attachment(content, content_type: str, fallback: str, filename: str):
    """日本語のファイル名を `filename*` で指定したダウンロード応答を返す。"""
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = (
        f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
    )
    return response


@api_view("GET")
def skillsheet_pdf(request):
    today = timezone.localdate()
    rendered = export.render_skillsheet(today)
    return _attachment(
        export.build_pdf(rendered.html),
        "application/pdf",
        "skillsheet.pdf",
        f"職務経歴書_{today:%Y%m%d}.pdf",
    )


@api_view("GET")
def skillsheet_markdown(request):
    today = timezone.localdate()
    rendered = export.render_skillsheet(today)
    return _attachment(
        rendered.markdown,
        "text/markdown; charset=utf-8",
        "skillsheet.md",
        f"職務経歴書_{today:%Y%m%d}.md",
    )


@api_view("POST")
def api_upload_image(request):
    """実績のサムネイル画像をアップロードする。保存先の相対パスを返す。"""
    path = uploads.save_work_image(request.FILES.get("image"))
    return _json({"path": path})
