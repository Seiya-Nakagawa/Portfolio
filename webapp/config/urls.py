from django.contrib import admin
from django.urls import path

from portfolio import views

# 本番は Ingress がパスプレフィックス（/portfolio）を除去して転送するため、
# ここではプレフィックスを含めずに定義する。
urlpatterns = [
    path("", views.index, name="index"),
    path("api/skills", views.api_skills, name="api-skills"),
    path("api/certifications", views.api_certifications, name="api-certifications"),
    path("api/works", views.api_works, name="api-works"),
    path("admin/", admin.site.urls),
]
