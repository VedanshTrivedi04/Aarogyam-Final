"""
apps/telegram_bot/models.py — Telegram conversational bot. Verification is
by email (matched against User.email, confirmed via a real emailed OTP —
Telegram has no way to prove email ownership on its own, unlike the native
phone-contact-share button).
"""
from django.db import models
from shared.models import BaseModel


TG_LANGUAGES = [('hi', 'Hindi'), ('en', 'English')]

TG_STATES = [
    ('IDLE',                    'Idle'),
    ('AWAITING_LANGUAGE',       'Awaiting Language Choice'),
    ('AWAITING_EMAIL',          'Awaiting Email'),
    ('AWAITING_OTP',            'Awaiting OTP'),
    ('AWAITING_DOSE_RESPONSE',  'Awaiting Dose Response'),
]

TG_DIRECTIONS = [('INBOUND', 'Inbound'), ('OUTBOUND', 'Outbound')]

TG_INTENTS = [
    ('DOSE_YES',  'Dose Taken'),
    ('DOSE_NO',   'Dose Not Taken'),
    ('DOSE_SKIP', 'Dose Skipped'),
    ('HELP',      'Help'),
    ('STATUS',    'Status Request'),
    ('REPORT',    'Adherence Report'),
    ('MENU',      'Main Menu'),
    ('UNKNOWN',   'Unknown'),
]


class TelegramSession(BaseModel):
    """One session per Telegram chat_id (not an email — that's only known
    after the user types it and gets matched/verified)."""
    chat_id          = models.CharField(max_length=32, unique=True, db_index=True)
    email             = models.EmailField(null=True, blank=True)
    language          = models.CharField(max_length=5, choices=TG_LANGUAGES, default='hi')
    user              = models.ForeignKey('identity.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='telegram_session')
    state             = models.CharField(max_length=30, choices=TG_STATES, default='IDLE')
    state_data        = models.JSONField(default=dict)
    last_activity_at  = models.DateTimeField()
    onboarding_done   = models.BooleanField(default=False)

    class Meta:
        db_table = 'telegram_sessions'

    def __str__(self):
        return f'TG {self.chat_id} [{self.state}]'


class TelegramInteractionLog(BaseModel):
    """Every inbound/outbound message, for idempotency and audit."""
    session             = models.ForeignKey(TelegramSession, on_delete=models.CASCADE, related_name='interactions')
    direction           = models.CharField(max_length=10, choices=TG_DIRECTIONS)
    message_body        = models.TextField()
    intent              = models.CharField(max_length=15, choices=TG_INTENTS, null=True, blank=True)
    telegram_update_id  = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'telegram_interaction_logs'
        constraints = [
            models.UniqueConstraint(
                fields=['telegram_update_id'],
                condition=models.Q(telegram_update_id__isnull=False),
                name='uq_tg_update_id',
            )
        ]

    def __str__(self):
        return f'{self.direction} [{self.intent}] — {self.session.chat_id}'
