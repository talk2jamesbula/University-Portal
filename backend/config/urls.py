from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.static import serve

admin.site.site_header = f"{settings.UNIVERSITY_NAME} Administration"
admin.site.site_title = f"{settings.UNIVERSITY_NAME} Admin"
admin.site.index_title = "Portal management"


def health(request):
    return JsonResponse({"status": "ok"})


def avatar_file(request, path):
    # Only the avatars folder is public; everything else in MEDIA_ROOT (payment proofs) is
    # served through permission-checked API views. In production, let the web server
    # serve /media/avatars/ directly for speed.
    return serve(request, path, document_root=Path(settings.MEDIA_ROOT) / "avatars")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.core.urls")),
    path("api/academics/", include("apps.academics.urls")),
    path("api/campus/", include("apps.campus.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/public/", include("apps.website.urls")),
    path("api/attendance/", include("apps.attendance.urls")),
    path("api/admissions/", include("apps.admissions.urls")),
    path("api/students/", include("apps.students.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/exams/", include("apps.exams.urls")),
    path("media/avatars/<path:path>", avatar_file),
]
