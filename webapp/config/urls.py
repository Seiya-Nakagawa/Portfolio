from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from portfolio import manage_views, views

# 本番は Ingress がパスプレフィックス（/portfolio）を除去して転送するため、
# ここではプレフィックスを含めずに定義する。
urlpatterns = [
    path("", views.index, name="index"),
    path("api/skills", views.api_skills, name="api-skills"),
    path("api/certifications", views.api_certifications, name="api-certifications"),
    path("api/works", views.api_works, name="api-works"),
    path("api/site", views.api_site, name="api-site"),
    # 登録画面（本人のログインが必要）
    path(
        "manage/login/",
        auth_views.LoginView.as_view(template_name="manage/login.html"),
        name="login",
    ),
    path("manage/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("manage/", manage_views.index, name="manage"),
    path(
        "manage/api/bootstrap", manage_views.api_bootstrap, name="manage-api-bootstrap"
    ),
    path("manage/api/projects", manage_views.api_projects, name="manage-api-projects"),
    path(
        "manage/api/projects/<str:project_id>",
        manage_views.api_project,
        name="manage-api-project",
    ),
    path("manage/api/skills", manage_views.api_skills, name="manage-api-skills"),
    path(
        "manage/api/categories",
        manage_views.api_categories,
        name="manage-api-categories",
    ),
    path(
        "manage/api/categories/order",
        manage_views.api_category_order,
        name="manage-api-category-order",
    ),
    path(
        "manage/api/categories/<str:category_name>",
        manage_views.api_category,
        name="manage-api-category",
    ),
    path(
        "manage/api/skills/<str:skill_id>",
        manage_views.api_skill,
        name="manage-api-skill",
    ),
    path(
        "manage/api/certifications",
        manage_views.api_certifications,
        name="manage-api-certifications",
    ),
    path(
        "manage/api/certifications/<int:certification_id>",
        manage_views.api_certification,
        name="manage-api-certification",
    ),
    path("manage/api/works", manage_views.api_works, name="manage-api-works"),
    path(
        "manage/api/works/<int:work_id>",
        manage_views.api_work,
        name="manage-api-work",
    ),
    path(
        "manage/api/companies",
        manage_views.api_companies,
        name="manage-api-companies",
    ),
    path(
        "manage/api/companies/<int:company_id>",
        manage_views.api_company,
        name="manage-api-company",
    ),
    path("manage/api/site", manage_views.api_site, name="manage-api-site"),
    path(
        "manage/api/uploads",
        manage_views.api_upload_image,
        name="manage-api-upload-image",
    ),
    path(
        "manage/api/skillsheet",
        manage_views.api_skillsheet,
        name="manage-api-skillsheet",
    ),
    path(
        "manage/api/skillsheet/texts/<str:text_key>",
        manage_views.api_skillsheet_text,
        name="manage-api-skillsheet-text",
    ),
    path(
        "manage/skillsheet.pdf",
        manage_views.skillsheet_pdf,
        name="manage-skillsheet-pdf",
    ),
    path(
        "manage/skillsheet.md",
        manage_views.skillsheet_markdown,
        name="manage-skillsheet-markdown",
    ),
    path("admin/", admin.site.urls),
]

# アップロードした画像を配信する。小規模な個人サイトのため、アプリケーションから直接配信する。
# 本番は Ingress がプレフィックスを除去して転送するため、プレフィックスを含めずに定義する。
urlpatterns += [
    path("media/<path:path>", views.media, name="media"),
]
