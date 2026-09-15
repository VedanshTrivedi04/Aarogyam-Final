"""
apps/agent_runtime/views.py
"""
import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from shared.pagination import StandardResultsPagination
from shared.response import APIResponse

from apps.agent_runtime.models import AgentAction
from apps.agent_runtime.serializers import AgentActionSerializer

logger = logging.getLogger("medadhere.agent_runtime.api")


class AgentActivityView(APIView):
    """
    GET /api/v1/agent-runtime/activity/<patient_id>/

    Read-only feed of what the Agentic AI Agent has done for a patient
    (reminders sent, caregiver alerts requested, doctor reviews flagged)
    and whether each action worked. Reuses HasPatientAccess from ai_engine
    — same self/caregiver/admin access rule the risk-score endpoint uses,
    not duplicated.
    """

    def get_permissions(self):
        from apps.ai_engine.api.views import HasPatientAccess
        return [IsAuthenticated(), HasPatientAccess()]

    def get(self, request, patient_id: str):
        try:
            qs = (
                AgentAction.objects.filter(goal__patient_id=patient_id)
                .select_related("goal", "outcome")
            )
            paginator = StandardResultsPagination()
            page = paginator.paginate_queryset(qs, request)
            return paginator.get_paginated_response(AgentActionSerializer(page, many=True).data)
        except Exception as e:
            logger.error(f"AgentActivityView failed for {patient_id}: {e}")
            return APIResponse.error("Agent activity temporarily unavailable", status=503)
