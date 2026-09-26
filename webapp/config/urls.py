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
    path("manage/api/site", manage_views.api_site, name="manage-api-site"),
    path("manage/api/export", manage_views.api_export, name="manage-api-export"),
    path(
        "manage/export.md", manage_views.export_download, name="manage-export-download"
    ),
    path("admin/", admin.site.urls),
]
