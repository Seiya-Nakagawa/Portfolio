from allauth.socialaccount import views as socialaccount_views
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from portfolio import account_views, manage_views, views
from portfolio import auth_views as portfolio_auth_views

# サービスホストのルート（/）で公開する。
urlpatterns = [
    path("", views.index, name="index"),
    # ユーザー別の公開ポートフォリオと読み取り専用 API（認証不要。公開中のユーザーのみ）
    path("u/<str:username>/", views.portfolio, name="portfolio"),
    path("u/<str:username>/api/skills", views.api_skills, name="api-skills"),
    path(
        "u/<str:username>/api/certifications",
        views.api_certifications,
        name="api-certifications",
    ),
    path("u/<str:username>/api/works", views.api_works, name="api-works"),
    path("u/<str:username>/api/site", views.api_site, name="api-site"),
    # ログイン・サインアップ（外部アカウントのみ。パスワードによるログインは提供しない）
    path("login/", portfolio_auth_views.login_page, name="login"),
    # 認証ライブラリが戻り先として逆引きする名前。同じログイン画面を指す。
    path("login/", portfolio_auth_views.login_page, name="account_login"),
    path("manage/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include(default_urlpatterns(GoogleProvider))),
    path("accounts/", include(default_urlpatterns(GitHubProvider))),
    path("accounts/signup/", socialaccount_views.signup, name="socialaccount_signup"),
    path(
        "accounts/login/cancelled/",
        socialaccount_views.login_cancelled,
        name="socialaccount_login_cancelled",
    ),
    path(
        "accounts/login/error/",
        socialaccount_views.login_error,
        name="socialaccount_login_error",
    ),
    path("accounts/reconsent/", portfolio_auth_views.reconsent, name="reconsent"),
    path("terms/", portfolio_auth_views.terms, name="terms"),
    path("privacy/", portfolio_auth_views.privacy, name="privacy"),
    # 登録画面（ログインが必要）
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
    path("manage/api/account", account_views.api_account, name="manage-api-account"),
    path(
        "manage/api/account/providers/<str:provider>",
        account_views.api_account_provider,
        name="manage-api-account-provider",
    ),
    path(
        "manage/api/account/withdraw",
        account_views.api_account_withdraw,
        name="manage-api-account-withdraw",
    ),
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
    # 管理サイトの独自のログイン画面は用いず、本サービスのログイン画面へ誘導する。
    path("admin/login/", RedirectView.as_view(pattern_name="login", query_string=True)),
    path("admin/", admin.site.urls),
]

# アップロードした画像を、公開設定と閲覧者を検証したうえでアプリケーションから配信する。
urlpatterns += [
    path("media/<path:path>", views.media, name="media"),
]
