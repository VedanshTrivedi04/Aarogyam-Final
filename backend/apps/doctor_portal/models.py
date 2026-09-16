"""
apps/doctor_portal/models.py — Phase 14: Doctor / Prescriber Portal
"""
from django.db import models
from shared.models import BaseModel


ALERT_THRESHOLDS = [
    ('ALL',    'All Alerts'),
    ('MEDIUM', 'Medium and Above'),
    ('HIGH',   'High and Critical Only'),
]


class DoctorProfile(BaseModel):
    user                = models.OneToOneField('identity.User', on_delete=models.CASCADE, related_name='doctor_profile')
    registration_number = models.CharField(max_length=50, unique=True)   # MCI number
    specialization      = models.CharField(max_length=100)
    hospital_name       = models.CharField(max_length=200, null=True, blank=True)
    is_verified         = models.BooleanField(default=False)
    verified_at         = models.DateTimeField(null=True, blank=True)

    # Display / discovery fields
    experience_years    = models.PositiveIntegerField(default=0)
    rating              = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)
    review_count        = models.PositiveIntegerField(default=0)
    consultation_fee    = models.PositiveIntegerField(default=300)  # INR
    is_available        = models.BooleanField(default=True)   # doctor's own "accepting calls/consults" toggle
    is_online           = models.BooleanField(default=False)  # live WS presence, set by NotificationConsumer
    last_seen_at        = models.DateTimeField(null=True, blank=True)
    next_slot           = models.CharField(max_length=100, blank=True, default='')
    languages           = models.JSONField(default=list, blank=True)

    def is_reachable_for_calls(self) -> bool:
        """Gate for starting a new call: must have the toggle on AND an open socket."""
        return self.is_available and self.is_online

    class Meta:
        db_table = 'doctor_profiles'

    def __str__(self):
        return f'Dr. {self.user.get_full_name()} ({self.registration_number})'


class DoctorPatientLink(BaseModel):
    """Patient explicitly links their doctor."""
    doctor                 = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='patient_links')
    patient                = models.ForeignKey('clinical.Patient', on_delete=models.CASCADE, related_name='doctor_links')
    linked_at              = models.DateTimeField(auto_now_add=True)
    can_view_adherence     = models.BooleanField(default=True)
    can_send_prescriptions = models.BooleanField(default=True)
    can_receive_alerts     = models.BooleanField(default=True)
    alert_threshold        = models.CharField(max_length=10, choices=ALERT_THRESHOLDS, default='HIGH')

    class Meta:
        db_table = 'doctor_patient_links'
        unique_together = ('doctor', 'patient')
        indexes  = [models.Index(fields=['patient', 'can_receive_alerts'])]

    def __str__(self):
        return f'{self.doctor} ↔ {self.patient}'


class DigitalPrescription(BaseModel):
    """Doctor sends a prescription directly via the app."""
    doctor                  = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name='digital_prescriptions')
    patient                 = models.ForeignKey('clinical.Patient', on_delete=models.PROTECT, related_name='digital_prescriptions')
    medication_name         = models.CharField(max_length=200)
    dosage                  = models.CharField(max_length=100)
    instructions            = models.TextField()
    instruction_points      = models.JSONField(default=list, blank=True)  # ["Take after food", "Avoid alcohol", ...]
    start_date              = models.DateField()
    end_date                = models.DateField(null=True, blank=True)
    notes                   = models.TextField(null=True, blank=True)
    compartment_number      = models.IntegerField(null=True, blank=True)
    current_pill_count      = models.IntegerField(null=True, blank=True)
    is_accepted             = models.BooleanField(null=True)     # None=pending, True=accepted, False=rejected
    accepted_at             = models.DateTimeField(null=True, blank=True)
    session                 = models.ForeignKey(
        'ConsultationSession', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='prescriptions'
    )
    converted_prescription  = models.OneToOneField(
        'clinical.Prescription', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='digital_source'
    )

    class Meta:
        db_table = 'doctor_digital_prescriptions'
        indexes  = [models.Index(fields=['patient', 'is_accepted'])]

    def __str__(self):
        return f'Digital Rx: {self.medication_name} → {self.patient}'


SESSION_STATUS = [
    ('REQUESTED', 'Requested'),
    ('ACCEPTED',  'Accepted'),
    ('ACTIVE',    'Active'),
    ('COMPLETED', 'Completed'),
    ('REJECTED',  'Rejected'),
]


class ConsultationSession(BaseModel):
    """Real-time consultation session between a doctor and patient."""
    doctor       = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='consultations')
    patient      = models.ForeignKey('clinical.Patient', on_delete=models.CASCADE, related_name='consultations')
    status       = models.CharField(max_length=12, choices=SESSION_STATUS, default='REQUESTED', db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at  = models.DateTimeField(null=True, blank=True)
    ended_at     = models.DateTimeField(null=True, blank=True)
    doctor_notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'doctor_consultation_sessions'
        indexes  = [models.Index(fields=['patient', 'status']),
                    models.Index(fields=['doctor', 'status'])]
        ordering = ['-requested_at']

    def __str__(self):
        return f'Session {self.id}: {self.doctor} ↔ {self.patient} [{self.status}]'


class ConsultationMessage(BaseModel):
    """A single chat message within a consultation session (text, file, or a structured card)."""
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('file', 'File'),
        ('adherence_request', 'Adherence Report Request'),
        ('adherence_report', 'Adherence Report'),
        ('prescription', 'Prescription'),
    ]

    session      = models.ForeignKey(ConsultationSession, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey('identity.User', on_delete=models.CASCADE)
    content      = models.TextField(blank=True, default='')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text', db_index=True)
    file_url     = models.CharField(max_length=1000, blank=True, null=True)
    file_name    = models.CharField(max_length=255, blank=True, null=True)
    file_size    = models.BigIntegerField(null=True, blank=True)
    mime_type    = models.CharField(max_length=120, blank=True, null=True)
    metadata     = models.JSONField(default=dict, blank=True)  # adherence data / prescription id / request id
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'doctor_consultation_messages'
        ordering = ['created_at']

    def __str__(self):
        return f'Msg in {self.session_id} by {self.sender_id}'


ADHERENCE_REQUEST_STATUS = [
    ('PENDING',  'Pending'),
    ('APPROVED', 'Approved'),
    ('DENIED',   'Denied'),
]


class AdherenceReportRequest(BaseModel):
    """A doctor's request to view a patient's adherence report, gated on patient approval."""
    session       = models.ForeignKey(ConsultationSession, on_delete=models.CASCADE, related_name='adherence_requests')
    requested_by  = models.ForeignKey('identity.User', on_delete=models.CASCADE, related_name='adherence_requests_made')
    status        = models.CharField(max_length=10, choices=ADHERENCE_REQUEST_STATUS, default='PENDING', db_index=True)
    responded_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'doctor_adherence_report_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'AdherenceRequest {self.id} [{self.status}] for session {self.session_id}'
