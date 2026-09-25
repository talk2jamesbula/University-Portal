from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import Requires

from .services import Analytics


class AnalyticsView(APIView):
    """Charts for the management dashboard, limited to what the viewer may see."""

    permission_classes = [Requires("reports.view")]

    def get(self, request):
        return Response(Analytics(request.user).build())
