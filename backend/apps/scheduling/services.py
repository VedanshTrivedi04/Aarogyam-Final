"""
apps/scheduling/services.py — Schedule generation, dose logging, snooze, adherence.
"""
import logging
from datetime import timedelta, datetime, date
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger('medadhere')


class ScheduleGenerationService:
    """
    Generates ReminderJob rows for a MedicationSchedule.
    Called:
      - When a Schedule is created / updated.
      - Daily by Celery Beat to fill 7-day rolling window.
      - When patient timezone changes.
    """

    @staticmethod
    def generate_upcoming_reminders(schedule, days: int = 7) -> int:
        from .models import ReminderJob
        from apps.clinical.models import MedicationSchedule, FrequencyType
        import pytz

        if not schedule.is_active:
            return 0

        rx       = schedule.prescription
        tz       = pytz.timezone(schedule.timezone)
        now_utc  = timezone.now()
        now_local = now_utc.astimezone(tz)
        end_local = now_local + timedelta(days=days)

        existing = set(
            ReminderJob.objects.filter(
                schedule=schedule,
                scheduled_at__gte=now_utc,
                status='PENDING',
            ).values_list('scheduled_at', flat=True)
        )

        times_of_day = schedule.times_of_day  # [{time, dose, with_food, label}]
        if not times_of_day:
            return 0

        created  = 0
        cursor   = now_local.date()
        deadline = end_local.date()

        while cursor <= deadline:
            if not ScheduleGenerationService._should_fire_on(schedule, cursor):
                cursor += timedelta(days=1)
                continue

            # Check prescription bounds
            if rx.start_date and cursor < rx.start_date:
                cursor += timedelta(days=1)
                continue
            if not rx.is_indefinite and rx.end_date and cursor > rx.end_date:
                break

            for slot in times_of_day:
                h, m = map(int, slot['time'].split(':'))
                local_dt  = tz.localize(datetime(cursor.year, cursor.month, cursor.day, h, m))
                utc_dt    = local_dt.astimezone(pytz.utc).replace(tzinfo=pytz.utc)

                if utc_dt in existing or utc_dt < now_utc:
                    continue

                job, was_created = ReminderJob.objects.get_or_create(
                    schedule=schedule,
                    scheduled_at=utc_dt,
                    defaults={
                        'window_start': utc_dt - timedelta(minutes=schedule.lead_minutes),
                        'window_end':   utc_dt + timedelta(minutes=60),
                        'dose_value':   Decimal(str(slot.get('dose', rx.dosage_value))),
                        'dose_unit':    rx.dosage_unit,
                        'with_food':    slot.get('with_food', rx.medication.requires_food),
                        'label':        slot.get('label', ''),
                        'status':       'PENDING',
                    }
                )
                if was_created:
                    created += 1
                    # Enqueue device commands for mapped devices/compartments, if any
                    try:
                        from apps.iot.models import DeviceCompartmentMapping, DeviceCommand
                        mappings = DeviceCompartmentMapping.objects.filter(
                            prescription=rx,
                            is_filled=True,
                        )
                        for m in mappings:
                            # Prepare compartment command (device should rotate to compartment and ready)
                            DeviceCommand.objects.create(
                                device=m.device,
                                command_type='PREPARE_COMPARTMENT',
                                payload={
                                    'compartment': m.compartment_number,
                                    'prescription_id': str(rx.id),
                                    'scheduled_at': utc_dt.isoformat(),
                                    'reason': 'SCHEDULED_DISPENSE',
                                },
                                expires_at=utc_dt + timedelta(minutes=60),
                            )
                            # Optionally instruct device to open gate at time of dispense
                            DeviceCommand.objects.create(
                                device=m.device,
                                command_type='OPEN_GATE',
                                payload={
                                    'compartment': m.compartment_number,
                                    'prescription_id': str(rx.id),
                                    'scheduled_at': utc_dt.isoformat(),
                                    'reason': 'SCHEDULED_DISPENSE_OPEN',
                                },
                                expires_at=utc_dt + timedelta(minutes=60),
                            )
                    except Exception:
                        # Keep schedule generation resilient — log elsewhere if needed
                        pass

            cursor += timedelta(days=1)

        return created

    @staticmethod
    def _should_fire_on(schedule, day: date) -> bool:
        from apps.clinical.models import FrequencyType
        ft = schedule.frequency_type

        if ft == FrequencyType.DAILY:
            return True
        if ft == FrequencyType.SPECIFIC_DAYS:
            return day.weekday() in schedule.days_of_week
        if ft == FrequencyType.EVERY_N_DAYS:
            start = schedule.prescription.start_date
            if not start:
                return True
            return (day - start).days % schedule.interval_days == 0
        if ft == FrequencyType.AS_NEEDED:
            return False  # PRN — logged manually
        if ft == FrequencyType.ONCE:
            return day == schedule.prescription.start_date
        if ft == FrequencyType.CYCLE:
            start  = schedule.prescription.start_date
            if not start:
                return True
            cycle  = (schedule.cycle_on_days or 0) + (schedule.cycle_off_days or 0)
            if cycle == 0:
                return True
            offset = (day - start).days % cycle
            return offset < (schedule.cycle_on_days or 0)
        return True

    @staticmethod
    def on_schedule_updated(schedule):
        """Cancel pending jobs and regenerate."""
        from .models import ReminderJob
        ReminderJob.objects.filter(schedule=schedule, status='PENDING').update(status='CANCELLED')
        return ScheduleGenerationService.generate_upcoming_reminders(schedule, days=30)

    @staticmethod
    def on_timezone_change(patient, new_tz: str):
        """Called when patient timezone changes — regenerate all active schedules."""
        from apps.clinical.models import MedicationSchedule, Prescription
        schedules = MedicationSchedule.objects.filter(
            prescription__patient=patient,
            prescription__is_active=True,
            is_active=True,
        )
        for schedule in schedules:
            schedule.timezone = new_tz
            schedule.save(update_fields=['timezone'])
            ScheduleGenerationService.on_schedule_updated(schedule)

    @staticmethod
    def fill_rolling_window():
        """Celery Beat: called hourly to ensure 7-day rolling window for all active schedules."""
        from apps.clinical.models import MedicationSchedule
        schedules = MedicationSchedule.objects.filter(
            is_active=True,
            prescription__is_active=True,
            prescription__deleted_at__isnull=True,
        )
        total = 0
        for schedule in schedules:
            try:
                total += ScheduleGenerationService.generate_upcoming_reminders(schedule, days=7)
            except Exception as e:
                logger.error(f'Schedule gen failed for schedule={schedule.id}: {e}')
        return total


class DoseLoggingService:
    """Handles dose acknowledgement, manual logging, snooze."""

    @staticmethod
    def log_dose(reminder_job, user, status: str, source: str = 'APP',
                 taken_at=None, notes: str = None, side_effects: str = None,
                 mood_score=None, pain_score=None, with_food: bool = None,
                 latitude=None, longitude=None) -> 'DoseLog':
        from .models import DoseLog, ReminderStatus

        valid_statuses = [ReminderStatus.TAKEN, ReminderStatus.MISSED, ReminderStatus.SKIPPED]
        if status not in valid_statuses:
            raise ValueError(f'Invalid status for dose log: {status}')

        if reminder_job.status in [ReminderStatus.TAKEN, ReminderStatus.MISSED]:
            raise ValueError('Dose already logged for this reminder.')

        now = timezone.now()
        reminder_job.status = status
        reminder_job.save(update_fields=['status', 'updated_at'])

        log = DoseLog.objects.create(
            reminder_job  = reminder_job,
            prescription  = reminder_job.schedule.prescription,
            logged_by     = user,
            status        = status,
            source        = source,
            taken_at      = taken_at or now,
            dose_value    = reminder_job.dose_value,
            dose_unit     = reminder_job.dose_unit,
            with_food     = with_food if with_food is not None else reminder_job.with_food,
            notes         = notes,
            side_effects  = side_effects,
            mood_score    = mood_score,
            pain_score    = pain_score,
            latitude      = latitude,
            longitude     = longitude,
        )

        # Update remaining quantity (deprecated)
        rx = reminder_job.schedule.prescription
        if status == 'TAKEN' and rx.remaining_quantity is not None:
            rx.remaining_quantity = max(Decimal('0'), rx.remaining_quantity - reminder_job.dose_value)
            rx.save(update_fields=['remaining_quantity', 'updated_at'])

        # New Hybrid Inventory Tracking
        if status == 'TAKEN' and rx.current_pill_count is not None and rx.current_pill_count > 0:
            rx.current_pill_count -= 1
            rx.save(update_fields=['current_pill_count', 'updated_at'])

            # Refill Alert logic
            if rx.current_pill_count <= 4:
                # Dispatch alert or notification here if necessary
                logger.info(f"Refill Alert: Prescription {rx.id} has low inventory ({rx.current_pill_count} pills).")

        # Double-Dosing Prevention: If logged manually but IoT is active, send cancel command
        if status == 'TAKEN' and source == 'APP':
            patient = rx.patient
            if not patient.is_travel_mode and rx.compartment_number:
                from apps.iot.models import Device, DeviceCommand
                device = Device.objects.filter(linked_patient=patient, is_active=True).first()
                if device:
                    DeviceCommand.objects.create(
                        device=device,
                        command_type='CANCEL_DISPENSE',
                        payload={
                            'compartment_number': rx.compartment_number,
                            'reason': 'dose_already_taken_manually'
                        },
                        expires_at=timezone.now() + timedelta(hours=1)
                    )
                    logger.info(f"Sent CANCEL_DISPENSE command to {device.id} for compartment {rx.compartment_number}.")

        # Broadcast
        try:
            from agenthandover import get_orchestrator
            get_orchestrator().broadcast('DOSE_LOGGED', {
                'patient_id':      str(reminder_job.patient.user.id),
                'prescription_id': str(rx.id),
                'medication':      rx.medication.name,
                'status':          status,
                'taken_at':        log.taken_at.isoformat(),
                'source':          source,
            })
        except Exception:
            pass

        return log

    @staticmethod
    def log_manual_dose(prescription, user, taken_at=None, dose_value=None,
                        notes=None, source='APP') -> 'DoseLog':
        """Log a PRN/as-needed dose without an associated reminder job."""
        from .models import DoseLog

        log = DoseLog.objects.create(
            reminder_job  = None,
            prescription  = prescription,
            logged_by     = user,
            status        = 'TAKEN',
            source        = source,
            taken_at      = taken_at or timezone.now(),
            dose_value    = dose_value or prescription.dosage_value,
            dose_unit     = prescription.dosage_unit,
            notes         = notes,
        )

        # Inventory Tracking for manual PRN dose
        if prescription.current_pill_count is not None and prescription.current_pill_count > 0:
            prescription.current_pill_count -= 1
            prescription.save(update_fields=['current_pill_count', 'updated_at'])

            # Refill Alert logic
            if prescription.current_pill_count <= 4:
                logger.info(f"Refill Alert: Prescription {prescription.id} has low inventory ({prescription.current_pill_count} pills).")

        return log

    @staticmethod
    def snooze(reminder_job, minutes: int = 10) -> 'ReminderJob':
        from .models import ReminderStatus

        if reminder_job.status != ReminderStatus.PENDING:
            raise ValueError('Only PENDING reminders can be snoozed.')
        if reminder_job.snooze_count >= 3:
            raise ValueError('Maximum snooze count (3) reached.')

        reminder_job.status       = ReminderStatus.SNOOZED
        reminder_job.snooze_until = timezone.now() + timedelta(minutes=minutes)
        reminder_job.snooze_count += 1
        reminder_job.save(update_fields=['status', 'snooze_until', 'snooze_count', 'updated_at'])
        return reminder_job


class AdherenceReportService:
    """Computes adherence metrics — used by dashboard, caregiver view, telemetry."""

    @staticmethod
    def get_summary(patient, days: int = 30) -> dict:
        from .models import DoseLog, ReminderJob
        from django.db.models import Count, Q

        since = timezone.now() - timedelta(days=days)

        totals = ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            scheduled_at__gte=since,
        ).aggregate(
            total     = Count('id'),
            taken     = Count('id', filter=Q(status='TAKEN')),
            missed    = Count('id', filter=Q(status='MISSED')),
            skipped   = Count('id', filter=Q(status='SKIPPED')),
            pending   = Count('id', filter=Q(status='PENDING')),
        )

        total = totals['total'] or 1
        adherence_pct = round((totals['taken'] / total) * 100, 1)

        return {
            'days':           days,
            'total_scheduled': totals['total'],
            'taken':           totals['taken'],
            'missed':          totals['missed'],
            'skipped':         totals['skipped'],
            'pending':         totals['pending'],
            'adherence_pct':   adherence_pct,
        }

    @staticmethod
    def get_timeline(patient, days: int = 30) -> list:
        """Per-day adherence breakdown for charts."""
        from .models import ReminderJob
        from django.db.models import Count, Q, functions
        from django.db.models.functions import TruncDate

        since = timezone.now() - timedelta(days=days)

        daily = (
            ReminderJob.objects
            .filter(schedule__prescription__patient=patient, scheduled_at__gte=since)
            .annotate(day=TruncDate('scheduled_at'))
            .values('day')
            .annotate(
                total   = Count('id'),
                taken   = Count('id', filter=Q(status='TAKEN')),
                missed  = Count('id', filter=Q(status='MISSED')),
                skipped = Count('id', filter=Q(status='SKIPPED')),
            )
            .order_by('day')
        )

        return [
            {
                'date':          str(r['day']),
                'total':         r['total'],
                'taken':         r['taken'],
                'missed':        r['missed'],
                'skipped':       r['skipped'],
                'adherence_pct': round((r['taken'] / r['total']) * 100, 1) if r['total'] else 0,
            }
            for r in daily
        ]

    @staticmethod
    def get_medication_breakdown(patient, days: int = 30) -> list:
        """Per-medication adherence breakdown."""
        from .models import ReminderJob
        from django.db.models import Count, Q

        since = timezone.now() - timedelta(days=days)

        meds = (
            ReminderJob.objects
            .filter(schedule__prescription__patient=patient, scheduled_at__gte=since)
            .values('schedule__prescription__id', 'schedule__prescription__medication__name')
            .annotate(
                total  = Count('id'),
                taken  = Count('id', filter=Q(status='TAKEN')),
                missed = Count('id', filter=Q(status='MISSED')),
            )
            .order_by('-total')
        )

        return [
            {
                'prescription_id': str(r['schedule__prescription__id']),
                'medication':      r['schedule__prescription__medication__name'],
                'total':           r['total'],
                'taken':           r['taken'],
                'missed':          r['missed'],
                'adherence_pct':   round((r['taken'] / r['total']) * 100, 1) if r['total'] else 0,
            }
            for r in meds
        ]
