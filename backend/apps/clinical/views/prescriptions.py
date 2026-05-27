"""
apps/clinical/views/prescriptions.py — Prescriptions and medication schedules.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from shared.response import APIResponse
from shared.permissions import IsPatient
from ..models import Patient, Prescription, MedicationSchedule
from ..serializers import (
    PrescriptionSerializer, PrescriptionCreateSerializer, PrescriptionUpdateSerializer,
    MedicationScheduleSerializer,
)
from ..services import PrescriptionService, DrugInteractionChecker


def get_patient_or_404(user):
    try:
        return user.patient_profile
    except Exception:
        from django.http import Http404
        raise Http404


# ─── Prescriptions ────────────────────────────────────────────────────────────

class PrescriptionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        """GET /api/v1/patients/me/prescriptions/"""
        patient = get_patient_or_404(request.user)
        qs = Prescription.objects.filter(
            patient=patient, deleted_at__isnull=True
        ).select_related('medication').prefetch_related('schedules')

        # Filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')

        return APIResponse.success(PrescriptionSerializer(qs, many=True).data)

    def post(self, request):
        """POST /api/v1/patients/me/prescriptions/"""
        patient = get_patient_or_404(request.user)
        s = PrescriptionCreateSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        # Drug interaction check
        interactions = DrugInteractionChecker.check(patient, s.validated_data['medication'].id)
        severe = [i for i in interactions if i['severity'] in ('SEVERE', 'CONTRAINDICATED')]

        try:
            prescription = PrescriptionService.create(patient, s.validated_data)
        except Exception as e:
            return APIResponse.error(str(e), code='PRESCRIPTION_FAILED')

        response_data = PrescriptionSerializer(prescription).data
        if interactions:
            response_data['drug_interaction_warnings'] = interactions
        if severe:
            response_data['severe_interaction_alert'] = True

        return APIResponse.created(response_data)


class PrescriptionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request, prescription_id):
        """GET /api/v1/patients/me/prescriptions/{id}/"""
        patient = get_patient_or_404(request.user)
        rx = get_object_or_404(Prescription, id=prescription_id, patient=patient, deleted_at__isnull=True)
        return APIResponse.success(PrescriptionSerializer(rx).data)

    def put(self, request, prescription_id):
        """PUT /api/v1/patients/me/prescriptions/{id}/"""
        patient = get_patient_or_404(request.user)
        rx = get_object_or_404(Prescription, id=prescription_id, patient=patient, deleted_at__isnull=True)
        s  = PrescriptionUpdateSerializer(rx, data=request.data, partial=True)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        s.save()
        return APIResponse.success(PrescriptionSerializer(rx).data, message='Prescription updated.')

    def delete(self, request, prescription_id):
        """DELETE /api/v1/patients/me/prescriptions/{id}/"""
        patient = get_patient_or_404(request.user)
        rx = Prescription.all_objects.filter(id=prescription_id, patient=patient).first()
        if not rx:
            return APIResponse.error("Prescription not found.", status=404)
        
        # Soft delete the prescription (also cancels pending reminders and triggers IoT cleanup)
        rx.soft_delete(user=request.user)
        
        return APIResponse.no_content('Prescription removed.')


# ─── Schedules ────────────────────────────────────────────────────────────────

class ScheduleListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request, prescription_id):
        """GET /api/v1/patients/me/prescriptions/{id}/schedules/"""
        patient = get_patient_or_404(request.user)
        rx = get_object_or_404(Prescription, id=prescription_id, patient=patient, deleted_at__isnull=True)
        schedules = MedicationSchedule.objects.filter(prescription=rx, deleted_at__isnull=True)
        return APIResponse.success(MedicationScheduleSerializer(schedules, many=True).data)

    def post(self, request, prescription_id):
        """POST /api/v1/patients/me/prescriptions/{id}/schedules/ — triggers reminder generation."""
        patient = get_patient_or_404(request.user)
        rx = get_object_or_404(Prescription, id=prescription_id, patient=patient, deleted_at__isnull=True)

        s = MedicationScheduleSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        # Default schedule timezone from patient timezone
        data = s.validated_data
        data.setdefault('timezone', patient.timezone)
        schedule = MedicationSchedule.objects.create(prescription=rx, **data)

        # Trigger reminder generation
        try:
            from apps.scheduling.services import ScheduleGenerationService
            ScheduleGenerationService.generate_upcoming_reminders(schedule, days=30)
        except Exception as e:
            import logging
            logging.getLogger('medadhere').error(f'Reminder generation failed: {e}')

        return APIResponse.created(MedicationScheduleSerializer(schedule).data)


class ScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def _get_schedule(self, request, prescription_id, schedule_id):
        patient = get_patient_or_404(request.user)
        rx = get_object_or_404(Prescription, id=prescription_id, patient=patient, deleted_at__isnull=True)
        return get_object_or_404(MedicationSchedule, id=schedule_id, prescription=rx, deleted_at__isnull=True)

    def put(self, request, prescription_id, schedule_id):
        """PUT /api/v1/patients/me/prescriptions/{id}/schedules/{sid}/"""
        schedule = self._get_schedule(request, prescription_id, schedule_id)
        s = MedicationScheduleSerializer(schedule, data=request.data, partial=True)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        s.save()

        # Regenerate reminders for updated schedule
        try:
            from apps.scheduling.services import ScheduleGenerationService
            ScheduleGenerationService.on_schedule_updated(schedule)
        except Exception:
            pass

        return APIResponse.success(MedicationScheduleSerializer(schedule).data, message='Schedule updated.')

    def delete(self, request, prescription_id, schedule_id):
        """DELETE /api/v1/patients/me/prescriptions/{id}/schedules/{sid}/"""
        schedule = self._get_schedule(request, prescription_id, schedule_id)
        # Cancel pending reminders
        from apps.scheduling.models import ReminderJob
        ReminderJob.objects.filter(schedule=schedule, status='PENDING').update(status='CANCELLED')
        schedule.is_active = False
        schedule.soft_delete()
        return APIResponse.no_content('Schedule removed.')
