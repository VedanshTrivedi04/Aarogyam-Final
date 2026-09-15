"""
apps/agent_runtime/urls.py
"""
from django.urls import path

from apps.agent_runtime.views import AgentActivityView

urlpatterns = [
    path("activity/<str:patient_id>/", AgentActivityView.as_view(), name="agent-activity"),
]
