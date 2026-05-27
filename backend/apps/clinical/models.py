"""
apps/clinical/models.py — Patient, Caregiver, Medications, Prescriptions, Schedules.
"""
import uuid
import secrets
from django.db import models
from django.utils import timezone
from shared.models import BaseModel


# ─── Patient ──────────────────────────────────────────────────────────────────
class CognitiveStatus(models.TextChoices):
    NORMAL   = 'NORMAL',   'Normal'
    MILD     = 'MILD',     'Mild Impairment'
    MODERATE = 'MODERATE', 'Moderate Impairment'
    SEVERE   = 'SEVERE',   'Severe Impairment'


class Patient(BaseModel):
    user              = models.OneToOneField('identity.User', on_delete=models.CASCADE, related_name='patient_profile')
    patient_code      = models.CharField(max_length=20, unique=True, db_index=True)
    date_of_birth     = models.DateField(null=True, blank=True)
    gender            = models.CharField(max_length=10, choices=[
                          ('M','Male'),('F','Female'),('O','Other'),('NS','Not Specified')
                        ], default='NS')
    blood_group       = models.CharField(max_length=5, blank=True, null=True)
    timezone          = models.CharField(max_length=100, default='Asia/Kolkata')
    primary_language  = models.CharField(max_length=10, default='en')
    emergency_contact_name  = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    # Hospitalization
    is_hospitalized       = models.BooleanField(default=False)
    hospitalized_since    = models.DateTimeField(null=True, blank=True)
    discharge_expected_at = models.DateTimeField(null=True, blank=True)
    hospital_name         = models.CharField(max_length=300, blank=True, null=True)
    # Accessibility flags
    cognitive_status      = models.CharField(max_length=20, choices=CognitiveStatus.choices, default=CognitiveStatus.NORMAL)
    has_vision_impairment  = models.BooleanField(default=False)
    has_hearing_impairment = models.BooleanField(default=False)
    requires_assistance    = models.BooleanField(default=False)
    # Hybrid IoT Support
    is_travel_mode         = models.BooleanField(default=False, help_text="If True, IoT device is ignored and scheduling relies entirely on the app.")

    class Meta:
        db_table = 'clinical_patients'

    def __str__(self):
        return f'{self.patient_code} — {self.user.full_name}'

    def save(self, *args, **kwargs):
        if not self.patient_code:
            self.patient_code = self._generate_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_code() -> str:
        return f'PA{secrets.token_hex(4).upper()}'


# ─── Patient Conditions (ICD-10) ──────────────────────────────────────────────
class PatientCondition(BaseModel):
    patient       = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='conditions')
    icd10_code    = models.CharField(max_length=10, blank=True, null=True)
    condition_name = models.CharField(max_length=300)
    severity      = models.CharField(max_length=20, choices=[
                      ('MILD','Mild'),('MODERATE','Moderate'),('SEVERE','Severe')
                    ], default='MILD')
    diagnosed_at  = models.DateField(null=True, blank=True)
    notes         = models.TextField(blank=True, null=True)
    is_active     = models.BooleanField(default=True)

    class Meta:
        db_table = 'clinical_patient_conditions'


# ─── Caregiver ────────────────────────────────────────────────────────────────
class Caregiver(BaseModel):
    user              = models.OneToOneField('identity.User', on_delete=models.CASCADE, related_name='caregiver_profile')
    is_professional   = models.BooleanField(default=False)
    specialty         = models.CharField(max_length=200, blank=True, null=True)
    license_number    = models.CharField(max_length=100, blank=True, null=True)
    organization_name = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        db_table = 'clinical_caregivers'

    def __str__(self):
        return f'Caregiver: {self.user.full_name}'


# ─── Patient–Caregiver Link ───────────────────────────────────────────────────
class PermissionLevel(models.TextChoices):
    VIEW_ONLY       = 'view_only',       'View Only'
    LOG_DOSES       = 'log_doses',       'Log Doses'
    MANAGE_SCHEDULE = 'manage_schedule', 'Manage Schedule'
    FULL_ACCESS     = 'full_access',     'Full Access'


class PatientCaregiverLink(BaseModel):
    patient          = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='caregiver_links')
    caregiver        = models.ForeignKey(Caregiver, on_delete=models.CASCADE, related_name='patient_links')
    permission_level = models.CharField(max_length=30, choices=PermissionLevel.choices, default=PermissionLevel.VIEW_ONLY)
    can_receive_alerts = models.BooleanField(default=True)
    is_active        = models.BooleanField(default=False)   # False until invite accepted
    invite_token     = models.CharField(max_length=100, unique=True, null=True, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at      = models.DateTimeField(null=True, blank=True)
    notes            = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'clinical_caregiver_links'
        unique_together = [('patient', 'caregiver')]

    def generate_invite_token(self):
        self.invite_token     = secrets.token_urlsafe(48)
        self.invite_expires_at = timezone.now() + __import__('datetime').timedelta(days=7)
        self.save(update_fields=['invite_token', 'invite_expires_at', 'updated_at'])
        return self.invite_token

    @property
    def is_invite_valid(self) -> bool:
        return bool(self.invite_token and self.invite_expires_at and
                    self.invite_expires_at > timezone.now())


# ─── Medication Catalog ───────────────────────────────────────────────────────
class MedicationForm(models.TextChoices):
    TABLET   = 'TABLET',   'Tablet'
    CAPSULE  = 'CAPSULE',  'Capsule'
    SYRUP    = 'SYRUP',    'Syrup'
    INJECTION = 'INJECTION','Injection'
    DROPS    = 'DROPS',    'Drops'
    INHALER  = 'INHALER',  'Inhaler'
    PATCH    = 'PATCH',    'Patch'
    CREAM    = 'CREAM',    'Cream'
    GEL      = 'GEL',      'Gel'
    POWDER   = 'POWDER',   'Powder'
    OTHER    = 'OTHER',    'Other'


class Medication(BaseModel):
    name              = models.CharField(max_length=300, db_index=True)
    generic_name      = models.CharField(max_length=300, blank=True, null=True)
    brand_name        = models.CharField(max_length=300, blank=True, null=True)
    drug_class        = models.CharField(max_length=200, blank=True, null=True)
    form              = models.CharField(max_length=20, choices=MedicationForm.choices, default=MedicationForm.TABLET)
    default_unit      = models.CharField(max_length=30, default='mg')
    strength          = models.CharField(max_length=50, blank=True, null=True)
    manufacturer      = models.CharField(max_length=300, blank=True, null=True)
    requires_food     = models.BooleanField(default=False)
    refrigeration_required = models.BooleanField(default=False)
    is_controlled_substance = models.BooleanField(default=False)
    barcode           = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    photo_url         = models.URLField(blank=True, null=True)
    description       = models.TextField(blank=True, null=True)
    side_effects      = models.TextField(blank=True, null=True)
    is_verified       = models.BooleanField(default=False)  # verified by pharmacist/admin

    class Meta:
        db_table = 'clinical_medications'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.form})'


class DrugInteraction(BaseModel):
    medication_a  = models.ForeignKey(Medication, on_delete=models.CASCADE, related_name='interactions_as_a')
    medication_b  = models.ForeignKey(Medication, on_delete=models.CASCADE, related_name='interactions_as_b')
    severity      = models.CharField(max_length=20, choices=[
                      ('MILD','Mild'),('MODERATE','Moderate'),('SEVERE','Severe'),('CONTRAINDICATED','Contraindicated')
                    ])
    description   = models.TextField()
    source        = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table    = 'clinical_drug_interactions'
        unique_together = [('medication_a', 'medication_b')]


class DrugInteractionCheckLog(BaseModel):
    patient            = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='interaction_logs')
    prescription_id    = models.UUIDField(null=True, blank=True)
    medications_checked = models.JSONField(default=list)
    interactions_found  = models.JSONField(default=list)
    has_severe         = models.BooleanField(default=False)
    api_source         = models.CharField(max_length=50, default='OPENFDA')

    class Meta:
        db_table = 'clinical_interaction_check_logs'


# ─── Prescription ─────────────────────────────────────────────────────────────
class Prescription(BaseModel):
    patient           = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    medication        = models.ForeignKey(Medication, on_delete=models.PROTECT, related_name='prescriptions')
    prescribed_by     = models.CharField(max_length=300, blank=True, null=True)   # Doctor name (free text)
    prescribing_doctor_id = models.UUIDField(null=True, blank=True)               # Future: link to HCP
    dosage_value      = models.DecimalField(max_digits=8, decimal_places=2)
    dosage_unit       = models.CharField(max_length=30, default='mg')
    instructions      = models.TextField(blank=True, null=True)
    start_date        = models.DateField()
    end_date          = models.DateField(null=True, blank=True)
    is_indefinite     = models.BooleanField(default=False)
    refill_alert_days = models.SmallIntegerField(default=7)
    total_quantity    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    remaining_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Compartment Mapping (Hybrid IoT feature)
    compartment_number = models.SmallIntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4')], null=True, blank=True)
    current_pill_count = models.PositiveIntegerField(default=0, help_text="Number of pills currently inside the mapped compartment")
    
    purpose           = models.CharField(max_length=500, blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    is_active         = models.BooleanField(default=True)
    photo_url         = models.URLField(blank=True, null=True)   # prescription image
    notes             = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'clinical_prescriptions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.patient.patient_code} — {self.medication.name} {self.dosage_value}{self.dosage_unit}'

    def soft_delete(self, user=None):
        """Override: also cancel all pending reminder jobs and clean up IoT mappings."""
        from apps.scheduling.models import ReminderJob
        ReminderJob.objects.filter(
            schedule__prescription=self, status='PENDING'
        ).update(status='CANCELLED')

        # Clean up IoT mappings and de-activate sub-compartments
        try:
            from apps.iot.models import Device, DeviceCompartmentMapping, PhysicalCompartment, SubCompartment, DeviceCommand
            from apps.iot.weight_service import calculate_compartment_expected_weight
            import datetime

            # Find the patient's active device
            device = Device.objects.filter(linked_patient=self.patient, is_active=True).first()
            if device:
                compartments_to_update = set()
                if self.compartment_number:
                    try:
                        compartments_to_update.add(int(self.compartment_number))
                    except (ValueError, TypeError):
                        pass

                mappings = DeviceCompartmentMapping.objects.filter(prescription=self)
                for mapping in mappings:
                    try:
                        compartments_to_update.add(int(mapping.compartment_number))
                    except (ValueError, TypeError):
                        pass

                for comp_num in compartments_to_update:
                    comp = PhysicalCompartment.objects.filter(device=device, compartment_number=comp_num).first()
                    if comp:
                        # Deactivate sub-compartments matching medicine name
                        SubCompartment.objects.filter(compartment=comp, medicine_name__iexact=self.medication.name).update(is_active=False)

                        # Recalculate compartment expected weight
                        active_subs = comp.sub_compartments.filter(is_active=True)
                        comp.expected_weight_grams = round(calculate_compartment_expected_weight(active_subs), 3)
                        comp.save(update_fields=['expected_weight_grams'])

                # Delete old-architecture DeviceCompartmentMapping entries
                mappings.delete()

                # Queue SYNC_SCHEDULE command to update device firmware
                DeviceCommand.objects.create(
                    device=device,
                    command_type='SYNC_SCHEDULE',
                    payload={
                        'reason': 'prescription_deleted',
                        'compartment': self.compartment_number,
                        'medicine': self.medication.name,
                    },
                    expires_at=timezone.now() + datetime.timedelta(hours=24),
                )
        except Exception as e:
            # We don't want an IoT sync cleanup error to block prescription soft deletion,
            # but we should log warning.
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'IoT sync failed for prescription deletion {self.id}: {e}')

        self.is_active = False
        super().soft_delete(user=user)


# ─── Medication Schedule ──────────────────────────────────────────────────────
class FrequencyType(models.TextChoices):
    DAILY       = 'DAILY',       'Every Day'
    SPECIFIC_DAYS = 'SPECIFIC_DAYS', 'Specific Days of Week'
    EVERY_N_DAYS  = 'EVERY_N_DAYS', 'Every N Days'
    AS_NEEDED   = 'AS_NEEDED',   'As Needed (PRN)'
    ONCE        = 'ONCE',        'One Time Only'
    CYCLE       = 'CYCLE',       'Cyclical (e.g. 21 on / 7 off)'


class MedicationSchedule(BaseModel):
    prescription  = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='schedules')
    frequency_type = models.CharField(max_length=20, choices=FrequencyType.choices, default=FrequencyType.DAILY)
    times_of_day  = models.JSONField(default=list)
    # Example: [{"time": "08:00", "dose": 1.0, "with_food": true, "label": "Morning"}]
    days_of_week  = models.JSONField(default=list)   # [0,1,2,3,4,5,6] — 0=Monday
    interval_days = models.SmallIntegerField(default=1)   # for EVERY_N_DAYS
    cycle_on_days = models.SmallIntegerField(null=True, blank=True)
    cycle_off_days = models.SmallIntegerField(null=True, blank=True)
    timezone      = models.CharField(max_length=100, default='Asia/Kolkata')
    is_active     = models.BooleanField(default=True)
    lead_minutes  = models.SmallIntegerField(default=5)   # notify X min before

    class Meta:
        db_table = 'clinical_medication_schedules'

    def __str__(self):
        return f'{self.prescription} — {self.frequency_type}'
