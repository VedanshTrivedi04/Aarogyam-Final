from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from shared.response import APIResponse
from .models import Streak, Badge, WeeklyAdherenceScore
from .serializers import StreakSerializer, BadgeSerializer, WeeklyAdherenceScoreSerializer


class GamificationViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        user = request.user
        # In a real app, user might have multiple patients if they are a caregiver,
        # but here we assume the user is the patient for MVP.
        patient = getattr(user, 'patient_profile', None)
        if not patient:
            return APIResponse.error("No patient profile found for this user", status=404)

        streak, _ = Streak.objects.get_or_create(patient=patient)
        badges = Badge.objects.filter(patient=patient).order_by('-earned_at')[:5]
        scores = WeeklyAdherenceScore.objects.filter(patient=patient).order_by('-week_start')[:4]

        return APIResponse.success({
            "streak": StreakSerializer(streak).data,
            "recent_badges": BadgeSerializer(badges, many=True).data,
            "recent_scores": WeeklyAdherenceScoreSerializer(scores, many=True).data,
        })

    @action(detail=False, methods=['post'])
    def ping_streak(self, request):
        """
        Manual check-in — registers today's activity for the streak without
        needing a real dose event. Routes through GamificationAgent
        (on_dose_logged), the single canonical streak/badge implementation
        also used by the real dose-taken/missed triggers.
        """
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return APIResponse.error("No patient profile found for this user", status=404)

        from agenthandover import AgentRegistry, HandoverPayload
        agent = AgentRegistry.get('GamificationAgent')
        agent.on_dose_logged(HandoverPayload(patient_id=str(patient.id), data={'status': 'TAKEN'}))

        streak = Streak.objects.get(patient=patient)
        return APIResponse.success(StreakSerializer(streak).data)


class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        patient = getattr(self.request.user, 'patient_profile', None)
        if not patient:
            return Badge.objects.none()
        return Badge.objects.filter(patient=patient).order_by('-earned_at')


class WeeklyScoreViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WeeklyAdherenceScoreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        patient = getattr(self.request.user, 'patient_profile', None)
        if not patient:
            return WeeklyAdherenceScore.objects.none()
        return WeeklyAdherenceScore.objects.filter(patient=patient).order_by('-week_start')
