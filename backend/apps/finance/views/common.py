from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header

User = get_user_model()


def owned_by_user(queryset, user):
    """Finance staff see every record; students only their own."""
    return queryset if user.has_permission("finance.view") else queryset.filter(student=user)


def resolve_student(request):
    """The signed-in student, or for finance staff the student given by ?student=<id>."""
    if request.user.has_permission("finance.view"):
        return get_object_or_404(User, pk=request.query_params.get("student"), role=User.Role.STUDENT)
    return request.user


def pdf_response(content, filename, request):
    response = HttpResponse(content, content_type="application/pdf")
    inline = request.query_params.get("inline") == "1"
    response["Content-Disposition"] = content_disposition_header(not inline, filename)
    return response
