"""
apps/notifications/models.py — Notification log, preferences, templates.
"""
from django.db import models
from shared.models import BaseModel


class NotificationChannel(models.TextChoices):
    PUSH        = 'PUSH',       'Push Notification (FCM/APNs)'
    EMAIL       = 'EMAIL',      'Email'
    SMS         = 'SMS',        'SMS'
    TELEGRAM    = 'TELEGRAM',   'Telegram'
    VOICE       = 'VOICE',      'Voice Call'
    IN_APP      = 'IN_APP',     'In-App'


class NotificationStatus(models.TextChoices):
    PENDING   = 'PENDING',   'Pending'
    SENT      = 'SENT',      'Sent'
    DELIVERED = 'DELIVERED', 'Delivered'
    READ      = 'READ',      'Read'
    FAILED    = 'FAILED',    'Failed'


class NotificationType(models.TextChoices):
    DOSE_REMINDER         = 'DOSE_REMINDER',         'Dose Reminder'
    MISSED_DOSE_ALERT     = 'MISSED_DOSE_ALERT',     'Missed Dose Alert'
    CAREGIVER_ALERT       = 'CAREGIVER_ALERT',       'Caregiver Alert'
    REFILL_ALERT          = 'REFILL_ALERT',          'Refill Alert'
    PRESCRIPTION_EXPIRY   = 'PRESCRIPTION_EXPIRY',   'Prescription Expiry'
    SUBSCRIPTION_EXPIRY   = 'SUBSCRIPTION_EXPIRY',   'Subscription Expiry'
    ANOMALY_ALERT         = 'ANOMALY_ALERT',         'Anomaly Alert'
    CAREGIVER_INVITE      = 'CAREGIVER_INVITE',      'Caregiver Invite'
    SYSTEM                = 'SYSTEM',                'System Notification'
    WELCOME               = 'WELCOME',               'Welcome'
    ACCOUNT_SECURITY      = 'ACCOUNT_SECURITY',      'Account Security'
    GEOFENCE_EXIT         = 'GEOFENCE_EXIT',         'Geofence Exit Alert'
    # AI Agent (apps.agent_runtime) — sent via agenthandover.NotificationAgent
    HIGH_RISK_ALERT       = 'HIGH_RISK_ALERT',       'High Risk Alert'
    DOCTOR_ALERT          = 'DOCTOR_ALERT',          'Doctor Review Alert'
    AI_INSIGHT            = 'AI_INSIGHT',            'AI Insight'
    AI_ADHERENCE_NUDGE    = 'AI_ADHERENCE_NUDGE',    'AI Adherence Nudge'
    AI_ADHERENCE_REMINDER = 'AI_ADHERENCE_REMINDER', 'AI Adherence Reminder'


# ─── In-App Notification (always stored regardless of channel) ────────────────
class Notification(BaseModel):
    user             = models.ForeignKey('identity.User', on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    channel          = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)
    status           = models.CharField(max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.PENDING)
    title            = models.CharField(max_length=300)
    body             = models.TextField()
    data             = models.JSONField(default=dict)    # deep link / action payload
    read_at          = models.DateTimeField(null=True, blank=True)
    sent_at          = models.DateTimeField(null=True, blank=True)
    delivered_at     = models.DateTimeField(null=True, blank=True)
    failed_reason    = models.TextField(blank=True, null=True)
    external_id      = models.CharField(max_length=300, blank=True, null=True)  # FCM message ID / SMS SID
    idempotency_key  = models.CharField(max_length=200, db_index=True, null=True, blank=True)

    class Meta:
        db_table = 'notifications_log'
        indexes  = [
            models.Index(fields=['user', 'status', '-created_at']),
            models.Index(fields=['user', 'read_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.channel}] {self.notification_type} → {self.user.email}'

    def mark_read(self):
        from django.utils import timezone
        self.read_at = timezone.now()
        self.status  = NotificationStatus.READ
        self.save(update_fields=['read_at', 'status', 'updated_at'])


# ─── Notification Template ────────────────────────────────────────────────────
class NotificationTemplate(BaseModel):
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices, unique=True)
    channel           = models.CharField(max_length=20, choices=NotificationChannel.choices)
    language          = models.CharField(max_length=10, default='en')
    subject_template  = models.CharField(max_length=500, blank=True)
    body_template     = models.TextField()
    is_active         = models.BooleanField(default=True)

    class Meta:
        db_table = 'notifications_templates'
        unique_together = [('notification_type', 'channel', 'language')]

    def render(self, context: dict) -> tuple[str, str]:
        """Returns (subject, body) with {{ var }} substitution."""
        from string import Template
        subj = self.subject_template
        body = self.body_template
        for k, v in context.items():
            subj = subj.replace(f'{{{{{k}}}}}', str(v))
            body = body.replace(f'{{{{{k}}}}}', str(v))
        return subj, body
