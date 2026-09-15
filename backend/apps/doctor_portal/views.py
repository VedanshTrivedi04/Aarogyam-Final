import os
from rest_framework import viewsets, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from .models import DoctorProfile, DoctorPatientLink, DigitalPrescription, ConsultationSession, ConsultationMessage
from .serializers import (
    DoctorProfileSerializer,
    DoctorPatientLinkSerializer,
    DigitalPrescriptionSerializer,
    ConsultationSessionSerializer,
    ConsultationMessageSerializer,
)


class DoctorProfileViewSet(viewsets.ModelViewSet):
    serializer_class   = DoctorProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'doctor_profile'):
            return DoctorProfile.objects.filter(user=user)
        # Patients / caregivers can see all verified doctors
        return DoctorProfile.objects.filter(is_verified=True)

    def perform_create(self, serializer):
        if DoctorProfile.objects.filter(user=self.request.user).exists():
            raise drf_serializers.ValidationError({'detail': 'Doctor profile already exists.'})
        serializer.save(user=self.request.user)


class DoctorPatientLinkViewSet(viewsets.ModelViewSet):
    serializer_class   = DoctorPatientLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'doctor_profile'):
            return DoctorPatientLink.objects.filter(
                doctor=user.doctor_profile
            ).select_related('doctor__user', 'patient__user')
        # Patient sees their own links
        return DoctorPatientLink.objects.filter(
            patient__user=user
        ).select_related('doctor__user', 'patient__user')

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'doctor_profile'):
            raise drf_serializers.ValidationError({'detail': 'Only doctors can create patient links.'})
        serializer.save(doctor=user.doctor_profile)

    @action(detail=True, methods=['get'])
    def adherence(self, request, pk=None):
        link = self.get_object()
        if not link.can_view_adherence:
            return Response({'detail': 'No permission to view adherence.'}, status=status.HTTP_403_FORBIDDEN)
        from apps.scheduling.services import AdherenceReportService
        report = AdherenceReportService.get_summary(link.patient, days=30)
        return Response(report)

    @action(detail=True, methods=['get'])
    def alerts(self, request, pk=None):
        link = self.get_object()
        if not link.can_receive_alerts:
            return Response({'detail': 'No permission to receive alerts.'}, status=status.HTTP_403_FORBIDDEN)
        from apps.scheduling.models import ReminderJob
        from apps.scheduling.serializers import ReminderJobSerializer
        missed = ReminderJob.objects.filter(
            schedule__prescription__patient=link.patient,
            status='MISSED',
        ).order_by('-scheduled_at')[:20]
        return Response(ReminderJobSerializer(missed, many=True).data)

    @action(detail=True, methods=['patch'], url_path='permissions')
    def update_permissions(self, request, pk=None):
        """PATCH .../links/{id}/permissions/ — update can_view_adherence etc."""
        link = self.get_object()
        allowed = {'can_view_adherence', 'can_send_prescriptions', 'can_receive_alerts', 'alert_threshold'}
        for field in allowed:
            if field in request.data:
                setattr(link, field, request.data[field])
        link.save()
        return Response(DoctorPatientLinkSerializer(link).data)


class DigitalPrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class   = DigitalPrescriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        patient_id = self.request.query_params.get('patient')

        if hasattr(user, 'doctor_profile'):
            qs = DigitalPrescription.objects.filter(doctor=user.doctor_profile)
        elif hasattr(user, 'caregiver_profile'):
            # Caregiver sees prescriptions for patients actively linked to them
            from apps.clinical.models import PatientCaregiverLink
            linked_patient_ids = PatientCaregiverLink.objects.filter(
                caregiver=user.caregiver_profile, is_active=True
            ).values_list('patient_id', flat=True)
            qs = DigitalPrescription.objects.filter(patient_id__in=linked_patient_ids)
        else:
            # Patient sees prescriptions sent to them
            qs = DigitalPrescription.objects.filter(patient__user=user)

        qs = qs.select_related('doctor__user', 'patient__user')
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'doctor_profile'):
            raise drf_serializers.ValidationError({'detail': 'Only doctors can create digital prescriptions.'})
        serializer.save(doctor=user.doctor_profile)

    @action(detail=True, methods=['patch'], url_path='accept')
    def accept(self, request, pk=None):
        """PATCH .../prescriptions/{id}/accept/ — patient accepts or rejects."""
        rx = self.get_object()
        decision = request.data.get('accepted')
        if decision is None:
            return Response({'detail': 'Provide accepted: true or false.'}, status=status.HTTP_400_BAD_REQUEST)
        rx.is_accepted = bool(decision)
        rx.accepted_at = timezone.now() if rx.is_accepted else None
        rx.save(update_fields=['is_accepted', 'accepted_at'])
        return Response(DigitalPrescriptionSerializer(rx).data)


# ── Consultation Sessions ────────────────────────────────────────────────────

class ConsultationSessionViewSet(viewsets.ModelViewSet):
    serializer_class   = ConsultationSessionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'doctor_profile'):
            return ConsultationSession.objects.filter(
                doctor=user.doctor_profile
            ).select_related('doctor__user', 'patient__user').prefetch_related('messages')
        if hasattr(user, 'patient_profile'):
            return ConsultationSession.objects.filter(
                patient=user.patient_profile
            ).select_related('doctor__user', 'patient__user').prefetch_related('messages')
        return ConsultationSession.objects.none()

    def perform_create(self, serializer):
        """Patient requests a consultation with a doctor."""
        user = self.request.user
        if not hasattr(user, 'patient_profile'):
            raise drf_serializers.ValidationError({'detail': 'Only patients can request consultations.'})
        doctor_id = self.request.data.get('doctor')
        try:
            doctor = DoctorProfile.objects.get(id=doctor_id)
        except DoctorProfile.DoesNotExist:
            raise drf_serializers.ValidationError({'detail': 'Doctor not found.'})
        # Prevent duplicate open sessions
        existing = ConsultationSession.objects.filter(
            doctor=doctor,
            patient=user.patient_profile,
            status__in=['REQUESTED', 'ACCEPTED', 'ACTIVE'],
        ).first()
        if existing:
            raise drf_serializers.ValidationError({'detail': 'An active session with this doctor already exists.', 'session_id': str(existing.id)})
        serializer.save(doctor=doctor, patient=user.patient_profile)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """POST .../consultations/{id}/accept/ — doctor accepts."""
        session = self.get_object()
        if not hasattr(request.user, 'doctor_profile') or session.doctor != request.user.doctor_profile:
            return Response({'detail': 'Only the assigned doctor can accept.'}, status=status.HTTP_403_FORBIDDEN)
        if session.status in ['ACTIVE', 'ACCEPTED']:
            return Response(ConsultationSessionSerializer(session, context={'request': request}).data)
        if session.status != 'REQUESTED':
            return Response({'detail': f'Cannot accept a session in {session.status} state.'}, status=status.HTTP_400_BAD_REQUEST)
        session.status      = 'ACTIVE'
        session.accepted_at = timezone.now()
        session.save(update_fields=['status', 'accepted_at'])
        return Response(ConsultationSessionSerializer(session, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """POST .../consultations/{id}/reject/ — doctor rejects."""
        session = self.get_object()
        if not hasattr(request.user, 'doctor_profile') or session.doctor != request.user.doctor_profile:
            return Response({'detail': 'Only the assigned doctor can reject.'}, status=status.HTTP_403_FORBIDDEN)
        if session.status not in ('REQUESTED',):
            return Response({'detail': 'Only REQUESTED sessions can be rejected.'}, status=status.HTTP_400_BAD_REQUEST)
        session.status   = 'REJECTED'
        session.ended_at = timezone.now()
        session.save(update_fields=['status', 'ended_at'])
        return Response(ConsultationSessionSerializer(session, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='end')
    def end(self, request, pk=None):
        """POST .../consultations/{id}/end/ — doctor ends session, optionally saves notes."""
        session = self.get_object()
        if not hasattr(request.user, 'doctor_profile') or session.doctor != request.user.doctor_profile:
            return Response({'detail': 'Only the assigned doctor can end the session.'}, status=status.HTTP_403_FORBIDDEN)
        if session.status not in ('ACTIVE', 'ACCEPTED'):
            return Response({'detail': 'Only ACTIVE sessions can be ended.'}, status=status.HTTP_400_BAD_REQUEST)
        session.status       = 'COMPLETED'
        session.ended_at     = timezone.now()
        session.doctor_notes = request.data.get('notes', session.doctor_notes)
        session.save(update_fields=['status', 'ended_at', 'doctor_notes'])
        return Response(ConsultationSessionSerializer(session, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='messages')
    def messages(self, request, pk=None):
        """GET .../consultations/{id}/messages/ — full chat history."""
        session = self.get_object()
        msgs    = session.messages.select_related('sender').order_by('created_at')
        return Response(ConsultationMessageSerializer(msgs, many=True, context={'request': request}).data)

    @action(
        detail=True, methods=['post'], url_path='upload',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request, pk=None):
        """POST .../consultations/{id}/upload/ — upload a file and persist as a message."""
        session = self.get_object()
        user    = request.user

        # Only session participants may upload
        is_doctor  = hasattr(user, 'doctor_profile') and session.doctor == user.doctor_profile
        is_patient = hasattr(user, 'patient_profile') and session.patient == user.patient_profile
        if not (is_doctor or is_patient):
            return Response({'detail': 'You are not part of this session.'}, status=status.HTTP_403_FORBIDDEN)

        if session.status not in ('ACTIVE', 'ACCEPTED'):
            return Response({'detail': 'Session is not active.'}, status=status.HTTP_400_BAD_REQUEST)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Save to disk under MEDIA_ROOT/consultations/<session_id>/
        rel_path  = f'consultations/{session.id}/{uploaded.name}'
        saved     = default_storage.save(rel_path, uploaded)
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        file_url  = request.build_absolute_uri(f'{media_url}{saved}')

        msg = ConsultationMessage.objects.create(
            session      = session,
            sender       = user,
            content      = '',
            message_type = 'file',
            file_url     = file_url,
            file_name    = uploaded.name,
            file_size    = uploaded.size,
            mime_type    = uploaded.content_type or 'application/octet-stream',
        )

        return Response({
            'file_url':  file_url,
            'file_name': uploaded.name,
            'file_size': uploaded.size,
            'mime_type': uploaded.content_type,
            'message_id': str(msg.id),
        }, status=status.HTTP_201_CREATED)
