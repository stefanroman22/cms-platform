from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from supabase import create_client


def _get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


class ProjectListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sb = _get_supabase()
        result = (
            sb.table("projects")
            .select("id, name, description, slug, is_active, created_at, updated_at")
            .eq("user_id", str(request.user.id))
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return Response(result.data)


class AccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sb = _get_supabase()
        user_result = (
            sb.table("users")
            .select("id, email, full_name, created_at")
            .eq("id", str(request.user.id))
            .single()
            .execute()
        )
        count_result = (
            sb.table("projects")
            .select("id", count="exact")
            .eq("user_id", str(request.user.id))
            .eq("is_active", True)
            .execute()
        )
        return Response({
            **user_result.data,
            "projects_count": count_result.count or 0,
        })


class ProjectRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        required = ["name", "type", "description"]
        for field in required:
            if not data.get(field):
                return Response({"detail": f"{field} is required."}, status=status.HTTP_400_BAD_REQUEST)

        sb = _get_supabase()
        sb.table("project_requests").insert({
            "user_id": str(request.user.id),
            "name": data["name"],
            "type": data["type"],
            "description": data["description"],
            "budget_range": data.get("budget_range") or None,
            "timeline": data.get("timeline") or None,
        }).execute()
        return Response({"success": True}, status=status.HTTP_201_CREATED)
