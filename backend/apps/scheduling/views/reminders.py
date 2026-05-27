"""
apps/scheduling/views/reminders.py — Reminder and dose-logging endpoints.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

import logging

from shared.response import APIResponse
from shared.permissions import IsPatient
from shared.pagination import StandardResultsPagination

logger = logging.getLogger('medadhere')
from ..models import ReminderJob
from ..serializers import (
    ReminderJobSerializer, LogDoseSerializer,
    ManualDoseSerializer, SnoozeSerializer, DoseLogSerializer,
)
from ..services import DoseLoggingService


def get_patient_or_404(user):
    try:
        return user.patient_profile
    except Exception:
        from django.http import Http404
        raise Http404


# ─── Today's Reminders ────────────────────────────────────────────────────────

class TodayRemindersView(APIView):
    """GET /api/v1/reminders/today/ — sorted PENDING/SNOOZED first, then TAKEN/MISSED."""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        import pytz
        import datetime
        patient = get_patient_or_404(request.user)

        # Use patient's timezone so "today" matches their local date, not UTC date
        patient_tz  = pytz.timezone(patient.timezone or 'Asia/Kolkata')
        now         = timezone.now()
        now_local   = now.astimezone(patient_tz)
        local_date  = now_local.date()
        today_start = patient_tz.localize(datetime.datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))
        today_end   = today_start + datetime.timedelta(days=1)

        # Auto-mark any PENDING/SENT dose as MISSED if 2 hours have passed since scheduled_at.
        # This runs even when Celery is not active, so the patient always sees correct status.
        missed_cutoff = now - datetime.timedelta(hours=2)
        ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            status__in=['PENDING', 'SENT'],
            scheduled_at__lte=missed_cutoff,
        ).update(status='MISSED', updated_at=now)

        # Dispatch due reminders only when a real Celery worker is running.
        # Skipped when CELERY_TASK_ALWAYS_EAGER=True (dev without worker) because
        # synchronous SMTP email sending inside an HTTP request causes 30s+ hangs.
        from django.conf import settings as _settings
        if not getattr(_settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            from ..tasks import _dispatch_single_reminder
            due_jobs = ReminderJob.objects.filter(
                schedule__prescription__patient=patient,
                status='PENDING',
                window_start__lte=now,
                scheduled_at__gte=now - datetime.timedelta(hours=1),
            ).values_list('id', flat=True)
            for job_id in due_jobs:
                try:
                    _dispatch_single_reminder.delay(str(job_id))
                except Exception:
                    pass

        jobs = ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            scheduled_at__gte=today_start,
            scheduled_at__lt=today_end,
        ).select_related(
            'schedule__prescription__medication',
            'schedule__prescription__patient',
        ).exclude(status='CANCELLED').order_by('scheduled_at')

        return APIResponse.success(ReminderJobSerializer(jobs, many=True).data)


class UpcomingRemindersView(APIView):
    """GET /api/v1/reminders/upcoming/?days=7 — paginated upcoming PENDING reminders."""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        patient = get_patient_or_404(request.user)
        days    = min(int(request.query_params.get('days', 7)), 30)
        now     = timezone.now()
        until   = now + __import__('datetime').timedelta(days=days)

        jobs = ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            scheduled_at__gte=now,
            scheduled_at__lt=until,
            status='PENDING',
        ).select_related(
            'schedule__prescription__medication',
        ).order_by('scheduled_at')

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(jobs, request)
        return paginator.get_paginated_response(ReminderJobSerializer(page, many=True).data)


class ReminderDetailView(APIView):
    """GET /api/v1/reminders/{id}/"""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request, reminder_id):
        patient = get_patient_or_404(request.user)
        job = get_object_or_404(
            ReminderJob,
            id=reminder_id,
            schedule__prescription__patient=patient,
        )
        return APIResponse.success(ReminderJobSerializer(job).data)


# ─── Dose Logging ─────────────────────────────────────────────────────────────

class LogDoseView(APIView):
    """POST /api/v1/reminders/{id}/log/ — TAKEN / MISSED / SKIPPED."""
    permission_classes = [IsAuthenticated]

    def post(self, request, reminder_id):
        # Allow both patient and caregiver (with LOG_DOSES or higher permission)
        patient = None
        try:
            patient = request.user.patient_profile
        except Exception:
            pass

        # Find the reminder
        job_qs = ReminderJob.objects.select_related(
            'schedule__prescription__patient__user',
            'schedule__prescription__medication',
        )
        if patient:
            job = get_object_or_404(job_qs, id=reminder_id, schedule__prescription__patient=patient)
        else:
            # Caregiver path — must have active link with LOG_DOSES+
            try:
                caregiver = request.user.caregiver_profile
            except Exception:
                return APIResponse.error('Not authorized.', status=403)
            job = get_object_or_404(job_qs, id=reminder_id)
            from apps.clinical.models import PatientCaregiverLink
            has_perm = PatientCaregiverLink.objects.filter(
                patient=job.schedule.prescription.patient,
                caregiver=caregiver,
                is_active=True,
                permission_level__in=['log_doses', 'manage_schedule', 'full_access'],
            ).exists()
            if not has_perm:
                return APIResponse.error('Insufficient caregiver permissions.', status=403)

        s = LogDoseSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        try:
            log = DoseLoggingService.log_dose(
                reminder_job=job,
                user=request.user,
                **s.validated_data,
            )
            return APIResponse.created(DoseLogSerializer(log).data, message='Dose logged.')
        except ValueError as e:
            return APIResponse.error(str(e), code='LOG_FAILED')


class SnoozeReminderView(APIView):
    """POST /api/v1/reminders/{id}/snooze/"""
    permission_classes = [IsAuthenticated, IsPatient]

    def post(self, request, reminder_id):
        patient = get_patient_or_404(request.user)
        job = get_object_or_404(
            ReminderJob,
            id=reminder_id,
            schedule__prescription__patient=patient,
        )
        s = SnoozeSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        try:
            job = DoseLoggingService.snooze(job, minutes=s.validated_data['minutes'])
            return APIResponse.success(
                {'snooze_until': job.snooze_until.isoformat(), 'snooze_count': job.snooze_count},
                message=f'Reminder snoozed for {s.validated_data["minutes"]} minutes.'
            )
        except ValueError as e:
            return APIResponse.error(str(e))


class TriggerDispatchView(APIView):
    """
    POST /api/v1/reminders/trigger-dispatch/
    Run the scheduling pipeline synchronously for the authenticated patient.
    Useful for testing without Celery Beat running.
    Creates reminder jobs for the next 7 days then dispatches any that are currently due.
    """
    permission_classes = [IsAuthenticated, IsPatient]

    def post(self, request):
        from apps.scheduling.services import ScheduleGenerationService
        from apps.scheduling.tasks import dispatch_due_reminders, fill_reminder_window
        from apps.clinical.models import MedicationSchedule

        patient = get_patient_or_404(request.user)

        # 1. Generate reminder jobs for all active schedules for this patient
        jobs_created = 0
        schedules = MedicationSchedule.objects.filter(
            prescription__patient=patient,
            is_active=True,
            prescription__is_active=True,
            prescription__deleted_at__isnull=True,
        )
        for schedule in schedules:
            try:
                jobs_created += ScheduleGenerationService.generate_upcoming_reminders(schedule, days=7)
            except Exception as e:
                logger.error(f'Reminder generation failed for schedule={schedule.id}: {e}')

        # 2. Dispatch any due PENDING reminders now (runs synchronously due to CELERY_TASK_ALWAYS_EAGER)
        result = dispatch_due_reminders()

        return APIResponse.success({
            'jobs_created': jobs_created,
            'dispatched':   result.get('dispatched', 0),
            'message':      'Check your email/in-app notifications.',
        })


class ManualDoseView(APIView):
    """POST /api/v1/doses/manual/ — PRN/as-needed or forgotten dose logging."""
    permission_classes = [IsAuthenticated, IsPatient]

    def post(self, request):
        patient = get_patient_or_404(request.user)
        s = ManualDoseSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        from apps.clinical.models import Prescription
        rx = get_object_or_404(
            Prescription,
            id=s.validated_data['prescription_id'],
            patient=patient,
            is_active=True,
        )
        log = DoseLoggingService.log_manual_dose(
            prescription=rx,
            user=request.user,
            taken_at=s.validated_data.get('taken_at'),
            dose_value=s.validated_data.get('dose_value'),
            notes=s.validated_data.get('notes'),
            source=s.validated_data.get('source', 'APP'),
        )
        return APIResponse.created(DoseLogSerializer(log).data, message='Manual dose recorded.')


class DispenseNowView(APIView):
    """POST /api/v1/reminders/{id}/dispense-now/ — Trigger immediate dispense on device."""
    permission_classes = [IsAuthenticated, IsPatient]

    def post(self, request, reminder_id):
        import datetime as dt
        patient = get_patient_or_404(request.user)
        job = get_object_or_404(
            ReminderJob,
            id=reminder_id,
            schedule__prescription__patient=patient,
        )

        from apps.iot.models import (
            Device, DeviceCommand, DeviceCompartmentMapping,
            PhysicalCompartment, DoseSession,
        )
        from apps.iot.weight_service import calculate_dose_expected_reduction

        # ── 1. Find the patient's active device ──────────────────────────────
        device = (
            Device.objects.filter(linked_patient=patient, is_active=True).first()
            or Device.objects.filter(user=request.user, is_active=True).first()
        )
        if not device:
            return APIResponse.error('No linked device found.', status=400)

        # ── 2. Resolve compartment number ────────────────────────────────────
        rx = job.schedule.prescription
        compartment_num = getattr(rx, 'compartment_number', None)

        # Fall back to old DeviceCompartmentMapping if prescription has no compartment_number
        if not compartment_num:
            mapping = DeviceCompartmentMapping.objects.filter(
                device=device,
                prescription=rx,
            ).first()
            if mapping:
                compartment_num = mapping.compartment_number

        if not compartment_num:
            return APIResponse.error(
                'Medication is not assigned to any compartment on the device. '
                'Ask your caregiver to complete the dispenser setup.',
                status=400,
            )

        # ── 3. Find the PhysicalCompartment (new IoT system) ─────────────────
        phys_comp = PhysicalCompartment.objects.filter(
            device=device,
            compartment_number=compartment_num,
            is_active=True,
        ).prefetch_related('sub_compartments').first()

        if not phys_comp:
            return APIResponse.error(
                f'Physical compartment {compartment_num} is not set up on this device. '
                'Ask your caregiver to complete the dispenser setup.',
                status=400,
            )

        # ── 4. Create (or reuse) a pending DoseSession ───────────────────────
        #  This is what makes GET .../schedule/current/ return has_dose: true
        #  immediately — even outside the normal ±10-minute slot window.
        now = timezone.now()
        active_subs = phys_comp.sub_compartments.filter(is_active=True)

        session, _ = DoseSession.objects.get_or_create(
            compartment=phys_comp,
            dose_status='pending',
            defaults={
                'scheduled_time': now,
                'expected_weight_before': phys_comp.current_balance_weight_grams,
                'weight_reduction_expected': calculate_dose_expected_reduction(active_subs),
            },
        )

        # ── 5. Queue OPEN_GATE command → ESP32 physically opens the lid ──────
        try:
            cmd = DeviceCommand.objects.create(
                device=device,
                command_type='OPEN_GATE',
                payload={
                    'compartment': compartment_num,
                    'session_id': str(session.id),
                    'scheduled_at': now.isoformat(),
                    'reason': 'manual_take_now',
                },
                issued_by=request.user,
                expires_at=now + dt.timedelta(minutes=10),
            )
            return APIResponse.success(
                {
                    'command_id': str(cmd.id),
                    'compartment': compartment_num,
                    'session_id': str(session.id),
                },
                message='Command sent to dispenser. Please bring your hand near the sensor.',
            )
        except Exception as e:
            logger.error(f'Failed to queue manual dispense for reminder {reminder_id}: {e}')
            return APIResponse.error('Failed to send command to device.', status=500)

