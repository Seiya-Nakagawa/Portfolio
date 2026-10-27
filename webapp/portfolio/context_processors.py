from django.conf import settings


def service(request):
    """全テンプレートで使うサービス共通の値。"""
    return {
        "service_name": settings.SERVICE_NAME,
        "service_description": settings.SERVICE_DESCRIPTION,
        "contact_form_url": settings.CONTACT_FORM_URL,
        "cloudflare_analytics_token": settings.CLOUDFLARE_ANALYTICS_TOKEN,
        # OGP・canonical は絶対 URL を要するため、クエリ文字列を除いたページの URL と
        # オリジンを渡す。
        "site_origin": f"{request.scheme}://{request.get_host()}",
        "canonical_url": request.build_absolute_uri(request.path),
    }
