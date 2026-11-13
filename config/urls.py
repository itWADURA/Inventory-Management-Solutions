from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import include, path


def health_check(request):
    """
    Lightweight healthcheck endpoint for load balancers and orchestrators.
    Does not disclose secrets or internal environment variables.
    """
    return JsonResponse({"status": "ok", "service": "itwadura-inventory", "version": "1.0.0"})


def offline_fallback_view(request):
    """Fallback page rendered by service worker when completely offline and page is not cached."""
    return render(request, "offline.html", status=503)


urlpatterns = [
    # Health check
    path("health/", health_check, name="health_check"),
    path("offline/", offline_fallback_view, name="offline_fallback"),
    # Django Administration
    path("admin/", admin.site.urls),
    # Application Modules
    path("accounts/", include("apps.accounts.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("reports/", include("apps.reports.urls")),
    path("audit/", include("apps.audit.urls")),
    path("", include("apps.organizations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
