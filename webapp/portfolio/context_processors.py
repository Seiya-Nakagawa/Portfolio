from django.conf import settings


def service(request):
    """全テンプレートで使うサービス共通の値。"""
    return {
        "service_name": settings.SERVICE_NAME,
        "contact_form_url": settings.CONTACT_FORM_URL,
    }
