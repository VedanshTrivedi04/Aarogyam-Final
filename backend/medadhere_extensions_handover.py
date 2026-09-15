"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         MEDADHERE — EXTENSIONS HANDOVER                                    ║
║         medadhere_extensions_handover.py                                   ║
║                                                                            ║
║  Purpose : Extension of agenthandover.py — 15 new feature domains.        ║
║  Integrates with existing AgentRegistry, AgentOrchestrator, and           ║
║  HandoverPayload contracts without modifying agenthandover.py.            ║
║                                                                            ║
║  PREREQUISITE : agenthandover.py must be bootstrapped first.              ║
║  CALL ORDER   : bootstrap_agents()            ← from agenthandover.py     ║
║                 bootstrap_extension_agents()  ← from this file            ║
║                 register_extension_events()   ← from this file            ║
║                                                                            ║
║  AI/ML EXCLUDED — stubs marked, AI team fills internals.                 ║
║                                                                            ║
║  NEW PHASES:                                                               ║
║    13. Pharmacy + Auto-Refill         → PharmacyAgent                     ║
║    14. Doctor / Prescriber Portal     → DoctorAgent                       ║
║    15. WhatsApp Bot (No-App Flow)     → WhatsAppBotAgent                  ║
║    16. Live Drug Interaction Check    → DrugInteractionAgent              ║
║    17. Family Multi-Patient Account   → FamilyAgent                       ║
║    18. FHIR / HL7 EHR Import         → FHIRAgent                         ║
║    19. Vital Signs Tracking           → VitalsAgent                       ║
║    20. Gamification + Nudges          → GamificationAgent                 ║
║    21. Side Effect + Pharmacovig.     → PharmacovigAgent                  ║
║    22. IVR Voice for Feature Phones   → (NotificationAgent extended)      ║
║    23. Pill Camera Verification       → (AdherenceAgent extended)         ║
║    24. Insurance Adherence Reports    → InsuranceReportsAgent             ║
║    25. Offline PWA Batch Sync         → (backend endpoint only)           ║
║    26. Geofencing Smart Reminders     → GeofenceAgent                     ║
║    27. ABHA + Govt Scheme Integration → ABHAAgent                         ║
║    28. Multi-Tenant Clinic Mode       → TenantAgent (Scale)               ║
║                                                                            ║
║  Stack : Django 5.x · DRF · PostgreSQL · Celery + Redis · JWT            ║
╚══════════════════════════════════════════════════════════════════════════════╝

TABLE OF CONTENTS
─────────────────
EXT-1.   New AgentNames
EXT-2.   New AgentEvents
EXT-3.   Orchestrator Event Registration (call register_extension_events())
EXT-4.   New Models Reference (all apps + schemas)
EXT-5.   New API Endpoints Reference
EXT-6.   PharmacyAgent       (Phase 13)
EXT-7.   DoctorAgent         (Phase 14)
EXT-8.   WhatsAppBotAgent    (Phase 15)
EXT-9.   DrugInteractionAgent(Phase 16)
EXT-10.  FamilyAgent         (Phase 17)
EXT-11.  FHIRAgent           (Phase 18)
EXT-12.  VitalsAgent         (Phase 19)
EXT-13.  GamificationAgent   (Phase 20)
EXT-14.  PharmacovigAgent    (Phase 21)
EXT-15.  InsuranceReportsAgent(Phase 24)
EXT-16.  GeofenceAgent       (Phase 26)
EXT-17.  ABHAAgent           (Phase 27)
EXT-18.  TenantAgent         (Phase 28)
EXT-19.  New Celery Tasks
EXT-20.  Extended Celery Beat Schedule
EXT-21.  New Management Commands
EXT-22.  New DB Indexes
EXT-23.  New Redis Cache Keys
EXT-24.  bootstrap_extension_agents()
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from celery import shared_task
from django.db import transaction
from django.utils import timezone

# ── Import from existing handover file ──────────────────────────────────────
from agenthandover import (
    AgentName,
    AgentEvent,
    AgentRegistry,
    AgentOrchestrator,
    HandoverPayload,
    HandoverResult,
    BaseAgent,
    orchestrator,
    SubscriptionLimitError,
)

logger = logging.getLogger('medadhere.extensions')


# ═══════════════════════════════════════════════════════════════════
# EXT-1. NEW AGENT NAMES
# ═══════════════════════════════════════════════════════════════════

# Extend AgentName enum by monkey-patching (Python Enum workaround)
# In production: add these directly to AgentName enum in agenthandover.py

PHARMACY_AGENT       = 'PharmacyAgent'
DOCTOR_AGENT         = 'DoctorAgent'
DRUG_INTERACT_AGENT  = 'DrugInteractionAgent'
FAMILY_AGENT         = 'FamilyAgent'
FHIR_AGENT           = 'FHIRAgent'
VITALS_AGENT         = 'VitalsAgent'
GAMIFICATION_AGENT   = 'GamificationAgent'
PHARMACOVIG_AGENT    = 'PharmacovigAgent'
INSURANCE_RPT_AGENT  = 'InsuranceReportsAgent'
GEOFENCE_AGENT       = 'GeofenceAgent'
ABHA_AGENT           = 'ABHAAgent'
TENANT_AGENT         = 'TenantAgent'


# ═══════════════════════════════════════════════════════════════════
# EXT-2. NEW AGENT EVENTS
# ═══════════════════════════════════════════════════════════════════

# Add these to AgentEvent enum in agenthandover.py

class ExtAgentEvent(str, Enum):
    """
    All new inter-agent events for extension features.
    Add to AgentEvent enum in agenthandover.py for full integration.
    """
    # ── Pharmacy / Refill ──────────────────────────────────────────
    REFILL_THRESHOLD_REACHED   = 'refill_threshold_reached'
    REFILL_ORDER_PLACED        = 'refill_order_placed'
    REFILL_ORDER_CONFIRMED     = 'refill_order_confirmed'
    REFILL_ORDER_DELIVERED     = 'refill_order_delivered'
    REFILL_ORDER_FAILED        = 'refill_order_failed'

    # ── Doctor Portal ─────────────────────────────────────────────
    DOCTOR_LINKED              = 'doctor_linked'
    DOCTOR_UNLINKED            = 'doctor_unlinked'
    DOCTOR_PRESCRIPTION_SENT   = 'doctor_prescription_sent'
    DOCTOR_ALERT_TRIGGERED     = 'doctor_alert_triggered'
    DOCTOR_REPORT_REQUESTED    = 'doctor_report_requested'

    # ── WhatsApp Bot ──────────────────────────────────────────────
    WHATSAPP_SESSION_STARTED   = 'whatsapp_session_started'
    WHATSAPP_DOSE_RESPONSE     = 'whatsapp_dose_response'
    WHATSAPP_ONBOARDING_DONE   = 'whatsapp_onboarding_done'
    WHATSAPP_HELP_REQUESTED    = 'whatsapp_help_requested'

    # ── Drug Interaction ──────────────────────────────────────────
    DRUG_INTERACTION_DETECTED  = 'drug_interaction_detected'
    DRUG_INTERACTION_CLEARED   = 'drug_interaction_cleared'
    DRUG_INTERACTION_SEVERE    = 'drug_interaction_severe'

    # ── Family ────────────────────────────────────────────────────
    FAMILY_GROUP_CREATED       = 'family_group_created'
    FAMILY_MEMBER_ADDED        = 'family_member_added'
    FAMILY_MEMBER_REMOVED      = 'family_member_removed'

    # ── FHIR ──────────────────────────────────────────────────────
    FHIR_SYNC_STARTED          = 'fhir_sync_started'
    FHIR_PRESCRIPTIONS_IMPORTED= 'fhir_prescriptions_imported'
    FHIR_SYNC_FAILED           = 'fhir_sync_failed'

    # ── Vitals ────────────────────────────────────────────────────
    VITAL_LOGGED               = 'vital_logged'
    VITAL_OUT_OF_RANGE         = 'vital_out_of_range'
    VITAL_TARGET_SET           = 'vital_target_set'

    # ── Gamification ──────────────────────────────────────────────
    STREAK_ACHIEVED            = 'streak_achieved'
    STREAK_BROKEN              = 'streak_broken'
    BADGE_EARNED               = 'badge_earned'
    MILESTONE_REACHED          = 'milestone_reached'
    WEEKLY_SCORE_COMPUTED      = 'weekly_score_computed'

    # ── Pharmacovigilance ─────────────────────────────────────────
    SIDE_EFFECT_REPORTED       = 'side_effect_reported'
    SEVERE_SIDE_EFFECT_DETECTED= 'severe_side_effect_detected'
    PHARMACOVIG_REPORT_EXPORTED= 'pharmacovig_report_exported'

    # ── IVR Voice ─────────────────────────────────────────────────
    IVR_CALL_INITIATED         = 'ivr_call_initiated'
    IVR_DOSE_CONFIRMED         = 'ivr_dose_confirmed'
    IVR_DOSE_DECLINED          = 'ivr_dose_declined'
    IVR_NO_RESPONSE            = 'ivr_no_response'

    # ── Pill Camera Verification ───────────────────────────────────
    PILL_VERIFICATION_REQUESTED= 'pill_verification_requested'
    PILL_VERIFICATION_PASSED   = 'pill_verification_passed'
    PILL_VERIFICATION_FAILED   = 'pill_verification_failed'

    # ── Insurance Reports ─────────────────────────────────────────
    REPORT_SHARE_CREATED       = 'report_share_created'
    REPORT_ACCESSED            = 'report_accessed'
    REPORT_REVOKED             = 'report_revoked'

    # ── Geofence ──────────────────────────────────────────────────
    GEOFENCE_EXIT_DETECTED     = 'geofence_exit_detected'
    GEOFENCE_ENTRY_DETECTED    = 'geofence_entry_detected'
    GEOFENCE_REMINDER_TRIGGERED= 'geofence_reminder_triggered'

    # ── ABHA ──────────────────────────────────────────────────────
    ABHA_LINKED                = 'abha_linked'
    ABHA_PRESCRIPTIONS_IMPORTED= 'abha_prescriptions_imported'
    ABHA_HEALTH_RECORD_SYNCED  = 'abha_health_record_synced'

    # ── Tenant ────────────────────────────────────────────────────
    TENANT_CREATED             = 'tenant_created'
    TENANT_PLAN_CHANGED        = 'tenant_plan_changed'
    TENANT_PATIENT_ADDED       = 'tenant_patient_added'


# ═══════════════════════════════════════════════════════════════════
# EXT-3. ORCHESTRATOR EVENT REGISTRATION
# Call register_extension_events() in CoreConfig.ready() AFTER
# bootstrap_extension_agents()
# ═══════════════════════════════════════════════════════════════════

def register_extension_events():
    """
    Registers all new event handlers into the existing orchestrator.
    Adds to orchestrator._event_handlers without overwriting existing entries.

    # apps/core/apps.py
    class CoreConfig(AppConfig):
        def ready(self):
            from agenthandover import bootstrap_agents
            from medadhere_extensions_handover import (
                bootstrap_extension_agents,
                register_extension_events,
            )
            bootstrap_agents()
            bootstrap_extension_agents()
            register_extension_events()
    """
    ext = {
        # ── Prescription created → drug interaction check ──────────
        # Merges with existing PRESCRIPTION_CREATED handlers
        ExtAgentEvent.DRUG_INTERACTION_DETECTED: [
            (DOCTOR_AGENT,        'alert_doctor_interaction'),
            (PHARMACY_AGENT,      'flag_interaction_on_refill'),
            (AUDIT_EXT,           'log_interaction_detected'),
        ],
        ExtAgentEvent.DRUG_INTERACTION_SEVERE: [
            (DOCTOR_AGENT,        'alert_doctor_interaction'),
            (PHARMACY_AGENT,      'block_refill_on_severe_interaction'),
            (AUDIT_EXT,           'log_severe_interaction'),
        ],

        # ── Refill ────────────────────────────────────────────────
        ExtAgentEvent.REFILL_THRESHOLD_REACHED: [
            (PHARMACY_AGENT,      'execute_refill_goal'),
            (NOTIFICATION_EXT,    'send_refill_reminder'),
        ],
        ExtAgentEvent.REFILL_ORDER_PLACED: [
            (NOTIFICATION_EXT,    'send_refill_confirmation'),
            (AUDIT_EXT,           'log_refill_order'),
        ],
        ExtAgentEvent.REFILL_ORDER_DELIVERED: [
            (PHARMACY_AGENT,      'update_prescription_quantity'),
            (NOTIFICATION_EXT,    'send_delivery_confirmation'),
            (GAMIFICATION_AGENT,  'award_refill_proactive_badge'),
        ],

        # ── Doctor alerts ─────────────────────────────────────────
        ExtAgentEvent.DOCTOR_ALERT_TRIGGERED: [
            (NOTIFICATION_EXT,    'send_doctor_alert'),
            (AUDIT_EXT,           'log_doctor_alert'),
        ],
        ExtAgentEvent.DOCTOR_PRESCRIPTION_SENT: [
            (DRUG_INTERACT_AGENT, 'check_new_prescription_interactions'),
            (GAMIFICATION_AGENT,  'award_digital_rx_badge'),
            (AUDIT_EXT,           'log_digital_prescription'),
        ],

        # ── Vitals ────────────────────────────────────────────────
        ExtAgentEvent.VITAL_OUT_OF_RANGE: [
            (DOCTOR_AGENT,        'alert_doctor_vital_oor'),
            (NOTIFICATION_EXT,    'send_vital_alert_to_patient'),
            (AUDIT_EXT,           'log_vital_oor'),
        ],

        # ── Gamification ──────────────────────────────────────────
        ExtAgentEvent.STREAK_ACHIEVED: [
            (NOTIFICATION_EXT,    'send_streak_celebration'),
        ],
        ExtAgentEvent.STREAK_BROKEN: [
            (NOTIFICATION_EXT,    'send_streak_broken_nudge'),
        ],
        ExtAgentEvent.BADGE_EARNED: [
            (NOTIFICATION_EXT,    'send_badge_notification'),
        ],
        ExtAgentEvent.MILESTONE_REACHED: [
            (NOTIFICATION_EXT,    'send_milestone_notification'),
            (INSURANCE_RPT_AGENT, 'update_adherence_score_snapshot'),
        ],

        # ── Dose logged → gamification hook ──────────────────────
        # (existing DOSE_LOGGED also triggers this now)
        ExtAgentEvent.SIDE_EFFECT_REPORTED: [
            (PHARMACOVIG_AGENT,   'record_and_assess'),
            (DOCTOR_AGENT,        'notify_doctor_side_effect'),
            (AUDIT_EXT,           'log_side_effect_report'),
        ],
        ExtAgentEvent.SEVERE_SIDE_EFFECT_DETECTED: [
            (DOCTOR_AGENT,        'urgent_alert_severe_side_effect'),
            (NOTIFICATION_EXT,    'send_emergency_side_effect_alert'),
            (PHARMACOVIG_AGENT,   'flag_for_cdsco_report'),
            (AUDIT_EXT,           'log_severe_side_effect'),
        ],

        # ── IVR ───────────────────────────────────────────────────
        ExtAgentEvent.IVR_NO_RESPONSE: [
            (NOTIFICATION_EXT,    'escalate_after_ivr_no_response'),
        ],

        # ── Geofence ──────────────────────────────────────────────
        ExtAgentEvent.GEOFENCE_EXIT_DETECTED: [
            (GEOFENCE_AGENT,      'evaluate_pending_doses_on_exit'),
        ],
        ExtAgentEvent.GEOFENCE_REMINDER_TRIGGERED: [
            (NOTIFICATION_EXT,    'send_geofence_reminder'),
            (AUDIT_EXT,           'log_geofence_trigger'),
        ],

        # ── ABHA ──────────────────────────────────────────────────
        ExtAgentEvent.ABHA_PRESCRIPTIONS_IMPORTED: [
            (DRUG_INTERACT_AGENT, 'check_imported_prescriptions'),
            (GAMIFICATION_AGENT,  'award_abha_linked_badge'),
            (AUDIT_EXT,           'log_abha_import'),
        ],

        # ── FHIR ──────────────────────────────────────────────────
        ExtAgentEvent.FHIR_PRESCRIPTIONS_IMPORTED: [
            (DRUG_INTERACT_AGENT, 'check_imported_prescriptions'),
            (AUDIT_EXT,           'log_fhir_import'),
        ],

        # ── Report sharing ────────────────────────────────────────
        ExtAgentEvent.REPORT_SHARE_CREATED: [
            (NOTIFICATION_EXT,    'send_report_share_notification'),
            (AUDIT_EXT,           'log_report_share_created'),
        ],
        ExtAgentEvent.REPORT_ACCESSED: [
            (NOTIFICATION_EXT,    'notify_patient_report_accessed'),
            (AUDIT_EXT,           'log_report_access'),
        ],

        # ── Tenant ────────────────────────────────────────────────
        ExtAgentEvent.TENANT_CREATED: [
            (NOTIFICATION_EXT,    'send_tenant_welcome'),
            (AUDIT_EXT,           'log_tenant_created'),
        ],
    }

    # Merge into orchestrator's existing handlers
    for event, handlers in ext.items():
        existing = orchestrator._event_handlers.get(event, [])
        orchestrator._event_handlers[event] = existing + handlers

    # Also extend existing PRESCRIPTION_CREATED to add drug interaction check
    from agenthandover import AgentEvent as AE
    orchestrator._event_handlers[AE.PRESCRIPTION_CREATED].extend([
        (DRUG_INTERACT_AGENT, 'check_new_prescription_interactions'),
    ])

    # Extend DOSE_LOGGED to trigger gamification
    orchestrator._event_handlers[AE.DOSE_LOGGED].extend([
        (GAMIFICATION_AGENT,  'on_dose_logged'),
    ])

    # Extend HIGH_RISK_DETECTED to alert doctor
    orchestrator._event_handlers[AE.HIGH_RISK_DETECTED].extend([
        (DOCTOR_AGENT,        'alert_doctor_high_risk'),
    ])

    logger.info('MedAdhere extension events registered.')


# Shorthand aliases (used in handler tuples above)
AUDIT_EXT         = 'AuditAgent'      # Reuse existing AuditAgent
NOTIFICATION_EXT  = 'NotificationAgent'


# ═══════════════════════════════════════════════════════════════════
# EXT-4. NEW MODELS REFERENCE
# ═══════════════════════════════════════════════════════════════════

"""
NEW APP DIRECTORIES:
    apps/pharmacy/          → PharmacyPartner, PharmacyIntegration, RefillOrder
    apps/doctor_portal/     → DoctorProfile, DoctorPatientLink, DigitalPrescription
    apps/whatsapp_bot/      → WhatsAppSession, WhatsAppConversationState
    apps/family/            → FamilyGroup, FamilyMember
    apps/fhir_integration/  → FHIRConnection, FHIRImportLog
    apps/vitals/            → VitalReading, VitalTarget
    apps/gamification/      → Streak, Badge, AdherenceScore, FamilyLeaderboard
    apps/pharmacovigilance/ → SideEffectReport, PharmacovigAggregate
    apps/insurance_reports/ → AdherenceReportShare, ReportAccessLog
    apps/geofence/          → GeofenceZone, GeofenceEvent
    apps/abha/              → ABHAConnection, ABHAImportLog
    apps/tenants/           → Tenant, TenantPlan, TenantAdmin

NEW DB SCHEMAS:
    pharmacy, doctor_portal, whatsapp_bot, family, fhir, vitals,
    gamification, pharmacovig, insurance_reports, geofence, abha, tenants

─────────────────────────────────────────────────────────────────────
PHASE 13: PHARMACY APP  (schema: pharmacy)
─────────────────────────────────────────────────────────────────────

class PharmacyPartner(BaseModel):
    # Registered pharmacy API partners (PharmEasy, 1mg, Netmeds)
    name            = CharField(max_length=100)        # 'PharmEasy'
    slug            = SlugField(unique=True)           # 'pharmeasy'
    api_base_url    = URLField()
    api_key_enc     = EncryptedTextField()             # AES-256
    webhook_secret  = EncryptedTextField()
    is_active       = BooleanField(default=True)
    supported_states= JSONField(default=list)          # ['MH','DL','KA',...]
    avg_delivery_hrs= PositiveIntegerField(default=48)
    class Meta: db_table = '"pharmacy"."pharmacy_partners"'

class PharmacyIntegration(BaseModel):
    # Patient's saved pharmacy preferences
    patient         = OneToOneField(Patient, on_delete=PROTECT)
    preferred_partner = ForeignKey(PharmacyPartner, on_delete=SET_NULL, null=True)
    delivery_address= JSONField()    # {line1, line2, city, state, pincode}
    saved_payment_method_id = CharField(null=True)  # gateway token
    auto_refill_enabled = BooleanField(default=False)
    class Meta: db_table = '"pharmacy"."pharmacy_integrations"'

class RefillOrder(BaseModel):
    # One auto-refill order per prescription per cycle
    prescription    = ForeignKey(Prescription, on_delete=PROTECT)
    patient         = ForeignKey(Patient, on_delete=PROTECT)
    partner         = ForeignKey(PharmacyPartner, on_delete=PROTECT)
    quantity_ordered= PositiveIntegerField()
    status          = CharField(choices=[
                        'PENDING','PARTNER_CONFIRMED','DISPATCHED',
                        'DELIVERED','FAILED','CANCELLED'])
    partner_order_id= CharField(null=True)   # External pharmacy order ID
    estimated_delivery = DateTimeField(null=True)
    delivered_at    = DateTimeField(null=True)
    total_amount    = DecimalField(max_digits=10, decimal_places=2)
    auto_triggered  = BooleanField(default=True)   # vs manual
    failure_reason  = TextField(null=True)
    class Meta:
        db_table = '"pharmacy"."refill_orders"'
        indexes = [Index(fields=['prescription', '-created_at'])]

─────────────────────────────────────────────────────────────────────
PHASE 14: DOCTOR PORTAL APP  (schema: doctor_portal)
─────────────────────────────────────────────────────────────────────

class DoctorProfile(BaseModel):
    user            = OneToOneField(User, on_delete=CASCADE)  # role=DOCTOR
    registration_number = CharField(unique=True)   # MCI number
    specialization  = CharField()
    hospital_name   = CharField(null=True)
    is_verified     = BooleanField(default=False)  # admin verifies
    verified_at     = DateTimeField(null=True)
    class Meta: db_table = '"doctor_portal"."doctor_profiles"'

class DoctorPatientLink(BaseModel):
    # Patient explicitly links their doctor
    doctor          = ForeignKey(DoctorProfile, on_delete=CASCADE)
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    linked_at       = DateTimeField(auto_now_add=True)
    can_view_adherence  = BooleanField(default=True)
    can_send_prescriptions = BooleanField(default=True)
    can_receive_alerts  = BooleanField(default=True)
    alert_threshold = CharField(choices=['HIGH','MEDIUM','ALL'], default='HIGH')
    class Meta:
        db_table = '"doctor_portal"."doctor_patient_links"'
        unique_together = ('doctor', 'patient')

class DigitalPrescription(BaseModel):
    # Doctor sends prescription directly via app
    doctor          = ForeignKey(DoctorProfile, on_delete=PROTECT)
    patient         = ForeignKey(Patient, on_delete=PROTECT)
    medication_name = CharField()
    dosage          = CharField()
    instructions    = TextField()
    start_date      = DateField()
    end_date        = DateField(null=True)
    notes           = TextField(null=True)
    is_accepted     = BooleanField(null=True)   # patient accept/reject
    accepted_at     = DateTimeField(null=True)
    converted_prescription = OneToOneField(Prescription, null=True, on_delete=SET_NULL)
    class Meta: db_table = '"doctor_portal"."digital_prescriptions"'

─────────────────────────────────────────────────────────────────────
PHASE 15: WHATSAPP BOT APP  (schema: whatsapp_bot)
─────────────────────────────────────────────────────────────────────

class WhatsAppSession(BaseModel):
    # One session per phone number
    phone_number    = CharField(unique=True)           # E.164 format
    user            = ForeignKey(User, null=True, on_delete=SET_NULL)
    state           = CharField()                      # See STATE_* constants
    state_data      = JSONField(default=dict)          # Context for current state
    last_activity_at= DateTimeField()
    onboarding_done = BooleanField(default=False)
    class Meta: db_table = '"whatsapp_bot"."whatsapp_sessions"'

# WhatsApp Conversation States
WA_STATE_IDLE          = 'IDLE'
WA_STATE_AWAITING_DOSE = 'AWAITING_DOSE_RESPONSE'   # sent reminder, waiting
WA_STATE_ONBOARDING_1  = 'ONBOARDING_LANGUAGE'
WA_STATE_ONBOARDING_2  = 'ONBOARDING_NAME'
WA_STATE_ONBOARDING_3  = 'ONBOARDING_PHONE_VERIFY'
WA_STATE_MENU          = 'MAIN_MENU'
WA_STATE_HELP          = 'HELP'

class WhatsAppInteractionLog(BaseModel):
    session         = ForeignKey(WhatsAppSession, on_delete=CASCADE)
    direction       = CharField(choices=['INBOUND', 'OUTBOUND'])
    message_body    = TextField()
    intent          = CharField(null=True)  # DOSE_YES/DOSE_NO/HELP/SKIP
    whatsapp_msg_id = CharField(null=True)  # WA message ID for dedup
    class Meta:
        db_table = '"whatsapp_bot"."interaction_logs"'
        unique_together = ('whatsapp_msg_id',)   # Idempotency

─────────────────────────────────────────────────────────────────────
PHASE 16: DRUG INTERACTION CHECK  (extend: clinical schema)
─────────────────────────────────────────────────────────────────────

class DrugInteractionCheckLog(BaseModel):
    # Audit of every real-time interaction check
    prescription    = ForeignKey(Prescription, on_delete=CASCADE)
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    medications_checked = JSONField()   # list of drug names checked
    interactions_found  = JSONField(default=list)
    has_severe      = BooleanField(default=False)
    api_source      = CharField()       # 'OPENFDA' / 'RXNORM' / 'LOCAL_DB'
    checked_at      = DateTimeField(auto_now_add=True)
    cache_hit       = BooleanField(default=False)
    class Meta: db_table = '"clinical"."drug_interaction_check_logs"'

# Extend existing DrugInteraction model with:
#   source = CharField(choices=['LOCAL','OPENFDA','RXNORM','DRUGBANK'])
#   rxcui_a = CharField(null=True)   # RxNorm concept unique identifier
#   rxcui_b = CharField(null=True)
#   last_verified_at = DateTimeField()

─────────────────────────────────────────────────────────────────────
PHASE 17: FAMILY APP  (schema: family)
─────────────────────────────────────────────────────────────────────

class FamilyGroup(BaseModel):
    name            = CharField(max_length=100)     # 'Sharma Family'
    owner           = ForeignKey(User, on_delete=PROTECT)
    class Meta: db_table = '"family"."family_groups"'

class FamilyMember(BaseModel):
    group           = ForeignKey(FamilyGroup, on_delete=CASCADE)
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    relationship    = CharField()  # 'father','mother','spouse','child','self'
    added_by        = ForeignKey(User, on_delete=PROTECT, related_name='+')
    class Meta:
        db_table = '"family"."family_members"'
        unique_together = ('group', 'patient')

# API: X-Patient-Context: {patient_uuid} header
# Middleware: FamilyContextMiddleware resolves patient from header
# Validates: requesting user is group owner or member

─────────────────────────────────────────────────────────────────────
PHASE 18: FHIR INTEGRATION  (schema: fhir)
─────────────────────────────────────────────────────────────────────

class FHIRConnection(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    fhir_server_url = URLField()        # 'https://fhir.apollo247.com/fhir/r4'
    access_token_enc= EncryptedTextField()
    refresh_token_enc=EncryptedTextField(null=True)
    token_expires_at= DateTimeField(null=True)
    hospital_name   = CharField()
    last_synced_at  = DateTimeField(null=True)
    sync_status     = CharField(choices=['IDLE','SYNCING','SUCCESS','FAILED'])
    class Meta: db_table = '"fhir"."fhir_connections"'

class FHIRImportLog(BaseModel):
    connection      = ForeignKey(FHIRConnection, on_delete=CASCADE)
    resource_type   = CharField()        # 'MedicationRequest'
    external_id     = CharField()        # FHIR resource ID
    raw_payload     = JSONField()
    import_status   = CharField(choices=['IMPORTED','DUPLICATE','REJECTED'])
    rejection_reason= TextField(null=True)
    created_prescription = ForeignKey(Prescription, null=True, on_delete=SET_NULL)
    class Meta: db_table = '"fhir"."fhir_import_logs"'

─────────────────────────────────────────────────────────────────────
PHASE 19: VITALS APP  (schema: vitals)
─────────────────────────────────────────────────────────────────────

VITAL_TYPE_BP_SYSTOLIC  = 'BP_SYSTOLIC'    # mmHg
VITAL_TYPE_BP_DIASTOLIC = 'BP_DIASTOLIC'   # mmHg
VITAL_TYPE_GLUCOSE      = 'GLUCOSE'        # mg/dL
VITAL_TYPE_SPO2         = 'SPO2'           # %
VITAL_TYPE_WEIGHT       = 'WEIGHT'         # kg
VITAL_TYPE_HEART_RATE   = 'HEART_RATE'     # bpm
VITAL_TYPE_TEMP         = 'TEMPERATURE'    # °C

class VitalReading(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    vital_type      = CharField()
    value           = DecimalField(max_digits=8, decimal_places=2)
    unit            = CharField()
    recorded_at     = DateTimeField()       # patient-reported time
    source          = CharField(choices=['MANUAL','DEVICE','HEALTHKIT','GOOGLEFIT'])
    device_brand    = CharField(null=True)  # 'Accu-Chek', 'Omron'
    prescription    = ForeignKey(Prescription, null=True, on_delete=SET_NULL)
    notes           = TextField(null=True)
    class Meta:
        db_table = '"vitals"."vital_readings"'
        indexes  = [Index(fields=['patient', 'vital_type', '-recorded_at'])]

class VitalTarget(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    vital_type      = CharField()
    target_min      = DecimalField(max_digits=8, decimal_places=2, null=True)
    target_max      = DecimalField(max_digits=8, decimal_places=2, null=True)
    set_by_doctor   = BooleanField(default=False)
    set_by          = ForeignKey(User, on_delete=PROTECT, null=True)
    class Meta:
        db_table = '"vitals"."vital_targets"'
        unique_together = ('patient', 'vital_type')

─────────────────────────────────────────────────────────────────────
PHASE 20: GAMIFICATION APP  (schema: gamification)
─────────────────────────────────────────────────────────────────────

BADGE_FIRST_DOSE        = 'FIRST_DOSE'
BADGE_7_DAY_STREAK      = '7_DAY_STREAK'
BADGE_30_DAY_STREAK     = '30_DAY_STREAK'
BADGE_PERFECT_WEEK      = 'PERFECT_WEEK'
BADGE_PERFECT_MONTH     = 'PERFECT_MONTH'
BADGE_DEVICE_LINKED     = 'DEVICE_LINKED'
BADGE_ABHA_LINKED       = 'ABHA_LINKED'
BADGE_DIGITAL_RX        = 'DIGITAL_RX'
BADGE_REFILL_PROACTIVE  = 'REFILL_PROACTIVE'  # ordered before running out
BADGE_CAREGIVER_HERO    = 'CAREGIVER_HERO'    # caregiver badges

class Streak(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    current_days    = PositiveIntegerField(default=0)
    longest_days    = PositiveIntegerField(default=0)
    last_dose_date  = DateField(null=True)
    last_broken_at  = DateTimeField(null=True)
    class Meta:
        db_table = '"gamification"."streaks"'
        unique_together = ('patient',)   # One streak record per patient

class Badge(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    badge_type      = CharField()
    earned_at       = DateTimeField(auto_now_add=True)
    class Meta:
        db_table = '"gamification"."badges"'
        unique_together = ('patient', 'badge_type')   # One per type per patient

class WeeklyAdherenceScore(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    week_start      = DateField()           # Always Monday
    score           = PositiveIntegerField()  # 0-100
    total_doses     = PositiveIntegerField()
    taken_doses     = PositiveIntegerField()
    missed_doses    = PositiveIntegerField()
    class Meta:
        db_table = '"gamification"."weekly_scores"'
        unique_together = ('patient', 'week_start')

─────────────────────────────────────────────────────────────────────
PHASE 21: PHARMACOVIGILANCE APP  (schema: pharmacovig)
─────────────────────────────────────────────────────────────────────

class SideEffectReport(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    prescription    = ForeignKey(Prescription, on_delete=CASCADE)
    symptom         = CharField()
    severity        = CharField(choices=['MILD','MODERATE','SEVERE','LIFE_THREATENING'])
    onset_at        = DateTimeField()
    resolved_at     = DateTimeField(null=True)
    is_ongoing      = BooleanField(default=True)
    reported_to_doctor = BooleanField(default=False)
    reported_to_cdsco  = BooleanField(default=False)   # India's drug regulator
    cdsco_report_id    = CharField(null=True)
    class Meta:
        db_table = '"pharmacovig"."side_effect_reports"'
        indexes  = [Index(fields=['prescription', '-created_at'])]

─────────────────────────────────────────────────────────────────────
PHASE 22: IVR VOICE  (extend: notifications schema)
─────────────────────────────────────────────────────────────────────

class IVRCallLog(BaseModel):
    # Extend notification schema
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    reminder_job    = ForeignKey(ReminderJob, null=True, on_delete=SET_NULL)
    twilio_call_sid = CharField(unique=True)
    phone_number    = CharField()
    status          = CharField(choices=['INITIATED','RINGING','IN_PROGRESS',
                                          'COMPLETED','NO_ANSWER','FAILED'])
    dtmf_response   = CharField(null=True)    # '1'=taken, '2'=skip, '3'=call caregiver
    response_intent = CharField(null=True)    # 'DOSE_TAKEN','DOSE_SKIPPED','ESCALATE'
    duration_secs   = PositiveIntegerField(null=True)
    class Meta: db_table = '"telemetry"."ivr_call_logs"'

─────────────────────────────────────────────────────────────────────
PHASE 23: PILL CAMERA VERIFICATION  (extend: telemetry schema)
─────────────────────────────────────────────────────────────────────

class DoseVerificationAttempt(BaseModel):
    adherence_event = OneToOneField(AdherenceEvent, on_delete=CASCADE)
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    method          = CharField(choices=['CAMERA','SELF_REPORT','IOT','IVR','WHATSAPP'])
    verification_passed = BooleanField(null=True)
    confidence_score    = FloatField(null=True)    # 0.0-1.0, from ML model
    pill_detected_name  = CharField(null=True)     # ML model output
    image_hash          = CharField(null=True)     # SHA-256, not the image itself
    class Meta: db_table = '"telemetry"."dose_verification_attempts"'

# Extend AdherenceEvent model fields:
#   verification_method = CharField(null=True)
#   verification_confidence = FloatField(null=True)
#   is_verified = BooleanField(default=False)

─────────────────────────────────────────────────────────────────────
PHASE 24: INSURANCE REPORTS APP  (schema: insurance_reports)
─────────────────────────────────────────────────────────────────────

class AdherenceReportShare(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    recipient_type  = CharField(choices=['INSURANCE','EMPLOYER','DOCTOR','SELF'])
    recipient_name  = CharField()
    access_token    = CharField(unique=True)     # UUID4 token, no auth needed
    expires_at      = DateTimeField()
    data_scope      = JSONField()   # {period_days: 90, include_conditions: false}
    is_revoked      = BooleanField(default=False)
    access_count    = PositiveIntegerField(default=0)
    class Meta: db_table = '"insurance_reports"."report_shares"'

class ReportAccessLog(BaseModel):
    share           = ForeignKey(AdherenceReportShare, on_delete=CASCADE)
    accessor_ip     = GenericIPAddressField()
    accessor_ua     = TextField()
    accessed_at     = DateTimeField(auto_now_add=True)
    class Meta: db_table = '"insurance_reports"."access_logs"'

─────────────────────────────────────────────────────────────────────
PHASE 25: OFFLINE PWA BATCH SYNC  (no new models — uses existing)
─────────────────────────────────────────────────────────────────────

# Frontend stores AdherenceEvents in IndexedDB when offline.
# On reconnect, sends batched payload to:
#   POST /api/v1/adherence/batch-sync/
# Backend processes each event idempotently using existing:
#   AdherenceEvent.objects.get_or_create(prescription, scheduled_at, ...)
# Returns per-item status: accepted / duplicate_ignored / rejected

─────────────────────────────────────────────────────────────────────
PHASE 26: GEOFENCE APP  (schema: geofence)
─────────────────────────────────────────────────────────────────────

ZONE_TYPE_HOME      = 'HOME'
ZONE_TYPE_WORK      = 'WORK'
ZONE_TYPE_GYM       = 'GYM'
ZONE_TYPE_CUSTOM    = 'CUSTOM'

class GeofenceZone(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    label           = CharField()       # 'Home', 'Office'
    zone_type       = CharField()
    latitude        = DecimalField(max_digits=10, decimal_places=7)
    longitude       = DecimalField(max_digits=10, decimal_places=7)
    radius_meters   = PositiveIntegerField(default=200)
    is_active       = BooleanField(default=True)
    # Processing is LOCAL on device — coordinates stored only for zone setup
    class Meta: db_table = '"geofence"."geofence_zones"'

class GeofenceEvent(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    zone            = ForeignKey(GeofenceZone, on_delete=CASCADE)
    event_type      = CharField(choices=['EXIT','ENTRY'])
    triggered_at    = DateTimeField()
    reminders_sent  = JSONField(default=list)   # list of reminder_job IDs sent
    class Meta: db_table = '"geofence"."geofence_events"'

─────────────────────────────────────────────────────────────────────
PHASE 27: ABHA INTEGRATION  (schema: abha)
─────────────────────────────────────────────────────────────────────

class ABHAConnection(BaseModel):
    patient         = ForeignKey(Patient, on_delete=CASCADE)
    abha_id         = CharField(unique=True)    # 14-digit ABHA number
    abha_address    = CharField(null=True)      # name@abdm
    linked_at       = DateTimeField(auto_now_add=True)
    consent_token_enc = EncryptedTextField(null=True)   # ABDM consent artifact
    last_synced_at  = DateTimeField(null=True)
    class Meta: db_table = '"abha"."abha_connections"'

class ABHAImportLog(BaseModel):
    connection      = ForeignKey(ABHAConnection, on_delete=CASCADE)
    record_type     = CharField()       # 'Prescription', 'DischargeSummary'
    source_hospital = CharField(null=True)
    raw_fhir_payload= JSONField()
    import_status   = CharField(choices=['IMPORTED','DUPLICATE','REJECTED'])
    created_prescription = ForeignKey(Prescription, null=True, on_delete=SET_NULL)
    class Meta: db_table = '"abha"."abha_import_logs"'

─────────────────────────────────────────────────────────────────────
PHASE 28: MULTI-TENANT APP  (schema: tenants)
─────────────────────────────────────────────────────────────────────

TENANT_PLAN_CLINIC      = 'CLINIC'
TENANT_PLAN_HOSPITAL    = 'HOSPITAL'
TENANT_PLAN_ENTERPRISE  = 'ENTERPRISE'

class Tenant(BaseModel):
    name            = CharField()
    subdomain       = SlugField(unique=True)   # 'appollo-indore.medadhere.in'
    logo_url        = URLField(null=True)
    plan            = CharField()
    max_patients    = PositiveIntegerField()
    is_active       = BooleanField(default=True)
    hipaa_baa_signed= BooleanField(default=False)
    baa_signed_at   = DateTimeField(null=True)
    class Meta: db_table = '"tenants"."tenants"'

class TenantAdmin(BaseModel):
    tenant          = ForeignKey(Tenant, on_delete=CASCADE)
    user            = ForeignKey(User, on_delete=CASCADE)
    is_primary      = BooleanField(default=False)
    class Meta:
        db_table = '"tenants"."tenant_admins"'
        unique_together = ('tenant', 'user')

# Row-level security: Add tenant FK to User, Patient, Prescription
# PostgreSQL RLS: CREATE POLICY tenant_isolation ON clinical.patients
#   USING (tenant_id = current_setting('app.tenant_id')::uuid)
# TenantMiddleware: sets search_path + app.tenant_id on each request
"""


# ═══════════════════════════════════════════════════════════════════
# EXT-5. NEW API ENDPOINTS REFERENCE
# ═══════════════════════════════════════════════════════════════════

"""
─────────────────────────────────────────────────────────────────────
PHASE 13: PHARMACY  /api/v1/pharmacy/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/pharmacy/partners/                   → list active partners
GET    /api/v1/pharmacy/integration/                → patient's pharmacy setup
PUT    /api/v1/pharmacy/integration/                → save delivery address + partner
POST   /api/v1/pharmacy/integration/auto-refill/    → enable/disable auto-refill
GET    /api/v1/pharmacy/refill-orders/              → patient's refill order history
POST   /api/v1/pharmacy/refill-orders/              → manual refill request
GET    /api/v1/pharmacy/refill-orders/{id}/         → single order detail
POST   /api/v1/pharmacy/refill-orders/{id}/cancel/  → cancel pending order
POST   /api/v1/pharmacy/webhook/{partner_slug}/     → partner delivery webhook (no auth)

─────────────────────────────────────────────────────────────────────
PHASE 14: DOCTOR PORTAL  /api/v1/doctor/ + /api/v1/patients/me/doctor/
─────────────────────────────────────────────────────────────────────
# Doctor-facing (role=DOCTOR required)
GET    /api/v1/doctor/profile/
PUT    /api/v1/doctor/profile/
GET    /api/v1/doctor/patients/                     → linked patients
GET    /api/v1/doctor/patients/{id}/adherence/      → adherence dashboard
GET    /api/v1/doctor/patients/{id}/vitals/         → vital readings
GET    /api/v1/doctor/patients/{id}/side-effects/   → reported side effects
POST   /api/v1/doctor/patients/{id}/prescriptions/  → send digital prescription
GET    /api/v1/doctor/alerts/                       → pending alerts

# Patient-facing
GET    /api/v1/patients/me/doctors/                 → linked doctors
POST   /api/v1/patients/me/doctors/link/            → link doctor by MCI number
DELETE /api/v1/patients/me/doctors/{id}/
GET    /api/v1/patients/me/digital-prescriptions/   → received digital Rx
POST   /api/v1/patients/me/digital-prescriptions/{id}/accept/
POST   /api/v1/patients/me/digital-prescriptions/{id}/reject/

─────────────────────────────────────────────────────────────────────
PHASE 15: WHATSAPP BOT  /api/v1/whatsapp/
─────────────────────────────────────────────────────────────────────
POST   /api/v1/whatsapp/webhook/                    → Twilio/WABA inbound webhook
POST   /api/v1/whatsapp/verify/                     → GET for WhatsApp webhook verify
# No patient-facing REST needed — all interaction via WhatsApp

─────────────────────────────────────────────────────────────────────
PHASE 16: DRUG INTERACTIONS  /api/v1/medications/interactions/
─────────────────────────────────────────────────────────────────────
POST   /api/v1/medications/interactions/check/      → check list of drug names
GET    /api/v1/patients/me/prescriptions/{id}/interactions/  → for one prescription

─────────────────────────────────────────────────────────────────────
PHASE 17: FAMILY  /api/v1/family/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/family/group/                        → my family group
POST   /api/v1/family/group/                        → create family group
GET    /api/v1/family/members/                      → list members
POST   /api/v1/family/members/                      → add member
DELETE /api/v1/family/members/{id}/
# Context switch: X-Patient-Context: {patient_uuid} on any /patients/me/ endpoint

─────────────────────────────────────────────────────────────────────
PHASE 18: FHIR  /api/v1/fhir/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/fhir/connections/
POST   /api/v1/fhir/connections/                    → connect FHIR server
DELETE /api/v1/fhir/connections/{id}/
POST   /api/v1/fhir/connections/{id}/sync/          → trigger manual sync
GET    /api/v1/fhir/import-logs/                    → what was imported

─────────────────────────────────────────────────────────────────────
PHASE 19: VITALS  /api/v1/patients/me/vitals/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/patients/me/vitals/
POST   /api/v1/patients/me/vitals/
GET    /api/v1/patients/me/vitals/{type}/           → e.g. /vitals/GLUCOSE/
GET    /api/v1/patients/me/vitals/{type}/history/
GET    /api/v1/patients/me/vitals/targets/
PUT    /api/v1/patients/me/vitals/targets/{type}/

─────────────────────────────────────────────────────────────────────
PHASE 20: GAMIFICATION  /api/v1/patients/me/gamification/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/patients/me/gamification/streak/
GET    /api/v1/patients/me/gamification/badges/
GET    /api/v1/patients/me/gamification/score/      → current week score
GET    /api/v1/patients/me/gamification/score/history/
GET    /api/v1/family/leaderboard/                  → family group leaderboard (opt-in)
POST   /api/v1/family/leaderboard/opt-in/
POST   /api/v1/family/leaderboard/opt-out/

─────────────────────────────────────────────────────────────────────
PHASE 21: SIDE EFFECTS  /api/v1/patients/me/side-effects/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/patients/me/side-effects/
POST   /api/v1/patients/me/side-effects/
GET    /api/v1/patients/me/side-effects/{id}/
PATCH  /api/v1/patients/me/side-effects/{id}/resolve/
# Admin only
GET    /admin/api/v1/pharmacovigilance/reports/     → aggregated CDSCO export

─────────────────────────────────────────────────────────────────────
PHASE 22: IVR CALL LOGS  (internal — no patient REST API)
─────────────────────────────────────────────────────────────────────
POST   /api/v1/ivr/webhook/response/                → Twilio TwiML callback
POST   /api/v1/ivr/webhook/status/                  → Twilio call status callback

─────────────────────────────────────────────────────────────────────
PHASE 23: PILL VERIFICATION  /api/v1/adherence/{id}/verify/
─────────────────────────────────────────────────────────────────────
POST   /api/v1/adherence/{id}/verify/               → submit image for verification
GET    /api/v1/adherence/{id}/verify/               → get verification status

─────────────────────────────────────────────────────────────────────
PHASE 24: INSURANCE REPORTS  /api/v1/patients/me/reports/share/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/patients/me/reports/shares/          → all active shares
POST   /api/v1/patients/me/reports/shares/          → create new share link
DELETE /api/v1/patients/me/reports/shares/{id}/     → revoke share
GET    /api/v1/reports/public/{token}/              → public access (no auth needed)

─────────────────────────────────────────────────────────────────────
PHASE 25: OFFLINE BATCH SYNC
─────────────────────────────────────────────────────────────────────
POST   /api/v1/adherence/batch-sync/
  Body: { "events": [ {prescription_id, scheduled_at, taken_at, status, log_method}, ... ] }
  Returns: { "results": [ {item_index, status: "accepted"|"duplicate_ignored"|"rejected"} ] }

─────────────────────────────────────────────────────────────────────
PHASE 26: GEOFENCE  /api/v1/patients/me/geofence/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/patients/me/geofence/zones/
POST   /api/v1/patients/me/geofence/zones/
PUT    /api/v1/patients/me/geofence/zones/{id}/
DELETE /api/v1/patients/me/geofence/zones/{id}/
POST   /api/v1/patients/me/geofence/event/          → mobile reports exit/entry

─────────────────────────────────────────────────────────────────────
PHASE 27: ABHA  /api/v1/abha/
─────────────────────────────────────────────────────────────────────
GET    /api/v1/abha/connection/
POST   /api/v1/abha/connect/                        → link ABHA ID (OTP flow)
POST   /api/v1/abha/connect/verify-otp/
DELETE /api/v1/abha/connection/
POST   /api/v1/abha/sync/                           → pull latest records from ABDM
GET    /api/v1/abha/import-logs/

─────────────────────────────────────────────────────────────────────
PHASE 28: MULTI-TENANT  /api/v1/tenant/ + /admin/api/v1/tenants/
─────────────────────────────────────────────────────────────────────
# Super admin only
POST   /admin/api/v1/tenants/                       → create tenant
GET    /admin/api/v1/tenants/
GET    /admin/api/v1/tenants/{id}/
PATCH  /admin/api/v1/tenants/{id}/
POST   /admin/api/v1/tenants/{id}/deactivate/
# Tenant admin (scoped to their tenant)
GET    /api/v1/tenant/dashboard/
GET    /api/v1/tenant/patients/
GET    /api/v1/tenant/adherence-summary/
"""


# ═══════════════════════════════════════════════════════════════════
# EXT-6. PHARMACY AGENT  (Phase 13)
# ═══════════════════════════════════════════════════════════════════

class PharmacyAgent(BaseAgent):
    """
    Owns: pharmacy partner registry, patient pharmacy preferences,
          auto-refill triggers, refill order lifecycle.

    Handover In:
        ← ClinicalApp (Celery Beat) : REFILL_THRESHOLD_REACHED — queues the
          agentic reason->plan->act refill pipeline (see
          apps/agent_runtime/services/pharmacy_pipeline.py) rather than
          deciding inline; the LLM call this triggers has real
          latency/failure modes that shouldn't block broadcast()'s
          synchronous loop.
        ← DrugInteractionAgent      : DRUG_INTERACTION_DETECTED (block refill if severe)
        ← StoreAgent                : ORDER_DELIVERED (update prescription quantity)

    Handover Out:
        → NotificationAgent : REFILL_ORDER_PLACED / REFILL_ORDER_DELIVERED
        → AuditAgent        : all refill actions
    """
    agent_name = PHARMACY_AGENT

    def execute_refill_goal(self, payload: HandoverPayload) -> dict:
        """
        Handler for REFILL_THRESHOLD_REACHED — the entry point for the
        agentic refill pipeline. Deliberately a thin enqueue, mirroring
        AIAgent.execute_intervention_goal. The actual observe->reason->
        plan->act->evaluate loop lives in apps.agent_runtime (see
        apps/agent_runtime/services/pharmacy_pipeline.py).
        """
        try:
            from apps.agent_runtime.tasks import evaluate_refill_needed
            evaluate_refill_needed.delay(
                payload.prescription_id, payload.patient_id, trace_id=payload.trace_id
            )
            return {'queued': True}
        except ImportError:
            # agent_runtime not installed/available — normal in standalone/test mode
            self.log('warning', 'agent_runtime not available — refill not queued', payload)
            return {'queued': False, 'reason': 'agent_runtime_unavailable'}

    def update_prescription_quantity(self, payload: HandoverPayload) -> dict:
        """Called when refill is delivered — replenishes prescription quantity."""
        from apps.pharmacy.models import RefillOrder
        from apps.clinical.models import Prescription

        order = RefillOrder.objects.select_related('prescription').get(
            id=payload.data['order_id']
        )
        Prescription.objects.filter(id=order.prescription_id).update(
            remaining_quantity=models.F('remaining_quantity') + order.quantity_ordered,
            updated_at=timezone.now(),
        )
        return {'status': 'quantity_updated', 'added': order.quantity_ordered}

    def flag_interaction_on_refill(self, payload: HandoverPayload) -> dict:
        """Moderate interaction — add warning note to any pending refill order."""
        from apps.pharmacy.models import RefillOrder
        RefillOrder.objects.filter(
            prescription_id=payload.prescription_id,
            status='PENDING',
        ).update(notes=f"Interaction warning: {payload.data.get('interaction_summary')}")
        return {'status': 'flagged'}

    def block_refill_on_severe_interaction(self, payload: HandoverPayload) -> dict:
        """Severe interaction — cancel any pending auto-refill order immediately."""
        from apps.pharmacy.models import RefillOrder
        cancelled = RefillOrder.objects.filter(
            prescription_id=payload.prescription_id,
            status='PENDING',
            auto_triggered=True,
        ).update(status='CANCELLED', failure_reason='SEVERE_DRUG_INTERACTION')
        self.log('warning', f'Refill blocked — severe interaction. Orders cancelled: {cancelled}', payload)
        return {'status': 'refill_blocked', 'cancelled_orders': cancelled}


# ═══════════════════════════════════════════════════════════════════
# EXT-7. DOCTOR AGENT  (Phase 14)
# ═══════════════════════════════════════════════════════════════════

class DoctorAgent(BaseAgent):
    """
    Owns: doctor-patient linking, digital prescriptions, doctor alerts.

    Handover In:
        ← AIAgent (via orchestrator)   : HIGH_RISK_DETECTED → alert_doctor_high_risk
        ← VitalsAgent                  : VITAL_OUT_OF_RANGE → alert_doctor_vital_oor
        ← PharmacovigAgent             : SEVERE_SIDE_EFFECT → urgent_alert_severe_side_effect
        ← DrugInteractionAgent         : INTERACTION_DETECTED → alert_doctor_interaction

    Handover Out:
        → NotificationAgent : all doctor notifications
        → MedicationAgent   : digital prescription → standard prescription flow
        → AuditAgent        : all doctor actions (PHI access)
    """
    agent_name = DOCTOR_AGENT

    def alert_doctor_high_risk(self, payload: HandoverPayload) -> dict:
        """
        Called when patient enters HIGH or CRITICAL risk level.
        Only alerts doctors who have can_receive_alerts=True and
        alert_threshold matches the risk level.
        """
        from apps.doctor_portal.models import DoctorPatientLink

        risk_level = payload.data.get('risk_level', 'HIGH')
        links = DoctorPatientLink.objects.filter(
            patient_id=payload.patient_id,
            can_receive_alerts=True,
        ).select_related('doctor__user')

        alerted = 0
        for link in links:
            if not self._threshold_met(link.alert_threshold, risk_level):
                continue
            notification_payload = HandoverPayload(
                user_id    = str(link.doctor.user_id),
                patient_id = payload.patient_id,
                data       = {
                    'alert_type'   : 'HIGH_RISK_PATIENT',
                    'risk_level'   : risk_level,
                    'patient_name' : payload.data.get('patient_name'),
                    'missed_doses' : payload.data.get('missed_doses'),
                    # Matches the real frontend route (frontend/src/routes/index.jsx:
                    # DoctorPatientDetail at '/doctor/patient/:id') — the previous
                    # '/doctor/patients/<id>/adherence/' path didn't exist.
                    'deep_link'    : f'/doctor/patient/{payload.patient_id}',
                },
                trace_id = payload.trace_id,
            )
            orchestrator.handover(
                DOCTOR_AGENT, NOTIFICATION_EXT,
                ExtAgentEvent.DOCTOR_ALERT_TRIGGERED, notification_payload,
            )
            alerted += 1

        self.log('info', f'Doctor high-risk alerts sent: {alerted}', payload)
        return {'doctors_alerted': alerted}

    def alert_doctor_vital_oor(self, payload: HandoverPayload) -> dict:
        """Called when a vital reading is outside the target range."""
        from apps.doctor_portal.models import DoctorPatientLink
        links = DoctorPatientLink.objects.filter(
            patient_id=payload.patient_id,
            can_receive_alerts=True,
            alert_threshold__in=['HIGH', 'ALL'],
        ).select_related('doctor__user')

        for link in links:
            notification_payload = HandoverPayload(
                user_id    = str(link.doctor.user_id),
                patient_id = payload.patient_id,
                data       = {
                    'alert_type' : 'VITAL_OUT_OF_RANGE',
                    'vital_type' : payload.data.get('vital_type'),
                    'value'      : payload.data.get('value'),
                    'target_max' : payload.data.get('target_max'),
                    'target_min' : payload.data.get('target_min'),
                },
                trace_id = payload.trace_id,
            )
            orchestrator.handover(
                DOCTOR_AGENT, NOTIFICATION_EXT,
                ExtAgentEvent.DOCTOR_ALERT_TRIGGERED, notification_payload,
            )
        return {'status': 'vital_oor_alert_sent'}

    def alert_doctor_interaction(self, payload: HandoverPayload) -> dict:
        """Alert doctor when a drug interaction is detected on their patient."""
        from apps.doctor_portal.models import DoctorPatientLink
        links = DoctorPatientLink.objects.filter(
            patient_id=payload.patient_id,
            can_receive_alerts=True,
        ).select_related('doctor__user')

        for link in links:
            notification_payload = HandoverPayload(
                user_id    = str(link.doctor.user_id),
                patient_id = payload.patient_id,
                data       = {
                    'alert_type'           : 'DRUG_INTERACTION',
                    'severity'             : payload.data.get('severity'),
                    'interaction_summary'  : payload.data.get('summary'),
                    'drug_a'               : payload.data.get('drug_a'),
                    'drug_b'               : payload.data.get('drug_b'),
                },
                trace_id = payload.trace_id,
            )
            orchestrator.handover(
                DOCTOR_AGENT, NOTIFICATION_EXT,
                ExtAgentEvent.DOCTOR_ALERT_TRIGGERED, notification_payload,
            )
        return {'status': 'interaction_alert_sent'}

    def notify_doctor_side_effect(self, payload: HandoverPayload) -> dict:
        """Notify linked doctors of a reported side effect."""
        return self.alert_doctor_vital_oor(payload)  # Same routing logic

    def urgent_alert_severe_side_effect(self, payload: HandoverPayload) -> dict:
        """Severe side effect — immediate alert via all channels (force override)."""
        from apps.doctor_portal.models import DoctorPatientLink
        links = DoctorPatientLink.objects.filter(
            patient_id=payload.patient_id,
            can_receive_alerts=True,
        ).select_related('doctor__user')

        for link in links:
            notification_payload = HandoverPayload(
                user_id    = str(link.doctor.user_id),
                patient_id = payload.patient_id,
                data       = {
                    'alert_type'   : 'SEVERE_SIDE_EFFECT',
                    'symptom'      : payload.data.get('symptom'),
                    'severity'     : 'SEVERE',
                    'force_channel': 'push,sms',  # Override quiet hours
                },
                trace_id = payload.trace_id,
            )
            orchestrator.handover(
                DOCTOR_AGENT, NOTIFICATION_EXT,
                ExtAgentEvent.DOCTOR_ALERT_TRIGGERED, notification_payload,
            )
        return {'status': 'severe_side_effect_alert_sent'}

    def accept_digital_prescription(self, prescription_id: str, patient_id: str) -> dict:
        """Patient accepts a digital prescription — converts to standard Prescription."""
        from apps.doctor_portal.models import DigitalPrescription
        from apps.clinical.services import PrescriptionService

        dp = DigitalPrescription.objects.select_related('doctor', 'patient').get(
            id=prescription_id, patient_id=patient_id
        )
        with transaction.atomic():
            prescription = PrescriptionService.create_from_digital(dp)
            dp.is_accepted = True
            dp.accepted_at = timezone.now()
            dp.converted_prescription = prescription
            dp.save(update_fields=['is_accepted', 'accepted_at', 'converted_prescription', 'updated_at'])

        payload = HandoverPayload(
            patient_id     = patient_id,
            prescription_id= str(prescription.id),
            data           = {'source': 'DIGITAL_PRESCRIPTION'},
        )
        orchestrator.broadcast(
            DOCTOR_AGENT,
            AgentEvent.PRESCRIPTION_CREATED,
            payload,
        )
        return {'prescription_id': str(prescription.id), 'status': 'accepted'}

    @staticmethod
    def _threshold_met(threshold: str, risk_level: str) -> bool:
        order = {'ALL': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
        return order.get(risk_level, 0) >= order.get(threshold, 3)


# ═══════════════════════════════════════════════════════════════════
# EXT-9. DRUG INTERACTION AGENT  (Phase 16)
# ═══════════════════════════════════════════════════════════════════

class DrugInteractionAgent(BaseAgent):
    """
    Owns: real-time drug interaction checks via OpenFDA / RxNorm.
    Called whenever a new prescription is created or imported.

    Cache strategy: interaction results cached 24h in Redis.
    Key: drug_interaction:{sorted_drug_a}:{sorted_drug_b}

    Handover In:
        ← MedicationAgent      : PRESCRIPTION_CREATED
        ← FHIRAgent            : FHIR_PRESCRIPTIONS_IMPORTED
        ← ABHAAgent            : ABHA_PRESCRIPTIONS_IMPORTED
        ← DoctorAgent          : DOCTOR_PRESCRIPTION_SENT

    Handover Out:
        → DoctorAgent          : DRUG_INTERACTION_DETECTED (moderate)
        → DoctorAgent          : DRUG_INTERACTION_SEVERE
        → NotificationAgent    : patient alert
        → AuditAgent           : all checks logged
    """
    agent_name = DRUG_INTERACT_AGENT

    SEVERITY_SEVERE    = 'SEVERE'
    SEVERITY_MODERATE  = 'MODERATE'
    SEVERITY_MILD      = 'MILD'

    CACHE_TTL_SECONDS  = 60 * 60 * 24  # 24 hours

    def check_new_prescription_interactions(self, payload: HandoverPayload) -> dict:
        """
        Main entry point — checks new prescription against ALL active medications
        of the same patient.
        """
        from apps.clinical.models import Prescription
        from django.core.cache import cache as django_cache

        new_rx = Prescription.objects.select_related('medication').get(
            id=payload.prescription_id
        )
        active_rxs = Prescription.objects.filter(
            patient_id=new_rx.patient_id,
            is_active=True,
        ).exclude(id=new_rx.id).select_related('medication')

        results = []
        has_severe = False

        for existing_rx in active_rxs:
            result = self._check_pair(new_rx.medication, existing_rx.medication)
            if result:
                results.append(result)
                if result['severity'] == self.SEVERITY_SEVERE:
                    has_severe = True

        if results:
            self._log_and_broadcast(payload, results, has_severe)

        return {'interactions_found': len(results), 'has_severe': has_severe}

    def check_imported_prescriptions(self, payload: HandoverPayload) -> dict:
        """
        Called after FHIR or ABHA import — batch check all imported prescriptions.
        """
        imported_ids = payload.data.get('prescription_ids', [])
        for rx_id in imported_ids:
            sub_payload = HandoverPayload(
                patient_id     = payload.patient_id,
                prescription_id= rx_id,
                trace_id       = payload.trace_id,
            )
            self.check_new_prescription_interactions(sub_payload)
        return {'prescriptions_checked': len(imported_ids)}

    def _check_pair(self, drug_a, drug_b) -> Optional[dict]:
        from django.core.cache import cache as django_cache
        from apps.clinical.services import OpenFDAInteractionService

        # Canonical cache key (alphabetical sort — order-independent)
        key_parts = sorted([drug_a.name.lower(), drug_b.name.lower()])
        cache_key = f"drug_interaction:{key_parts[0]}:{key_parts[1]}"

        cached = django_cache.get(cache_key)
        if cached is not None:
            return cached  # None = no interaction (also cached)

        result = OpenFDAInteractionService.check(drug_a, drug_b)
        django_cache.set(cache_key, result, self.CACHE_TTL_SECONDS)
        return result

    def _log_and_broadcast(self, payload: HandoverPayload, results: list, has_severe: bool):
        from apps.clinical.models import DrugInteractionCheckLog

        DrugInteractionCheckLog.objects.create(
            prescription_id   = payload.prescription_id,
            patient_id        = payload.patient_id,
            medications_checked=[r['drug_names'] for r in results],
            interactions_found= results,
            has_severe        = has_severe,
            api_source        = 'OPENFDA',
        )
        event = (ExtAgentEvent.DRUG_INTERACTION_SEVERE if has_severe
                 else ExtAgentEvent.DRUG_INTERACTION_DETECTED)

        broadcast_payload = HandoverPayload(
            patient_id     = payload.patient_id,
            prescription_id= payload.prescription_id,
            data           = {
                'interactions' : results,
                'has_severe'   : has_severe,
                'severity'     : self.SEVERITY_SEVERE if has_severe else self.SEVERITY_MODERATE,
                'summary'      : results[0].get('description', '') if results else '',
                'drug_a'       : results[0].get('drug_a', '') if results else '',
                'drug_b'       : results[0].get('drug_b', '') if results else '',
            },
            trace_id = payload.trace_id,
        )
        orchestrator.broadcast(DRUG_INTERACT_AGENT, event, broadcast_payload)


# ═══════════════════════════════════════════════════════════════════
# EXT-10. FAMILY AGENT  (Phase 17)
# ═══════════════════════════════════════════════════════════════════

class FamilyAgent(BaseAgent):
    """
    Owns: family group creation, member management, patient context switching.

    The X-Patient-Context header is resolved by FamilyContextMiddleware
    before hitting any view — no agent logic needed for context switching.

    Handover In:
        ← AuthAgent : USER_REGISTERED → initialize_family_if_needed
    Handover Out:
        → NotificationAgent : member invite notifications
        → AuditAgent        : all family actions
    """
    agent_name = FAMILY_AGENT

    def create_group(self, owner_user_id: str, name: str) -> dict:
        from apps.family.models import FamilyGroup, FamilyMember
        from apps.clinical.models import Patient

        with transaction.atomic():
            group = FamilyGroup.objects.create(
                name=name, owner_id=owner_user_id
            )
            # Add the owner's own patient profile as first member
            try:
                patient = Patient.objects.get(user_id=owner_user_id)
                FamilyMember.objects.create(
                    group=group, patient=patient,
                    relationship='self', added_by_id=owner_user_id,
                )
            except Patient.DoesNotExist:
                pass

        payload = HandoverPayload(
            user_id=owner_user_id,
            data={'group_id': str(group.id), 'group_name': name},
        )
        orchestrator.broadcast(FAMILY_AGENT, ExtAgentEvent.FAMILY_GROUP_CREATED, payload)
        return {'group_id': str(group.id)}

    def add_member(self, group_id: str, patient_id: str,
                   relationship: str, added_by_id: str) -> dict:
        from apps.family.models import FamilyGroup, FamilyMember

        group = FamilyGroup.objects.get(id=group_id, owner_id=added_by_id)
        member, created = FamilyMember.objects.get_or_create(
            group=group, patient_id=patient_id,
            defaults={'relationship': relationship, 'added_by_id': added_by_id},
        )
        if not created:
            return {'status': 'already_member'}

        payload = HandoverPayload(
            user_id    = added_by_id,
            patient_id = patient_id,
            data       = {'group_id': group_id, 'relationship': relationship},
        )
        orchestrator.broadcast(FAMILY_AGENT, ExtAgentEvent.FAMILY_MEMBER_ADDED, payload)
        return {'member_id': str(member.id), 'status': 'added'}


# ═══════════════════════════════════════════════════════════════════
# EXT-11. FHIR AGENT  (Phase 18)
# ═══════════════════════════════════════════════════════════════════

class FHIRAgent(BaseAgent):
    """
    Owns: FHIR R4 server connections, MedicationRequest import pipeline.

    FHIR Resource handled: MedicationRequest → Prescription
    Deduplication: FHIRImportLog.external_id (unique per connection)

    Handover In:
        ← Celery Beat  : scheduled sync
        ← Patient      : manual sync trigger

    Handover Out:
        → DrugInteractionAgent : FHIR_PRESCRIPTIONS_IMPORTED
        → ReminderAgent        : via PRESCRIPTION_CREATED broadcast
        → AuditAgent           : import log
    """
    agent_name = FHIR_AGENT

    def sync_connection(self, connection_id: str, triggered_by: str = 'SCHEDULED') -> dict:
        from apps.fhir_integration.models import FHIRConnection, FHIRImportLog
        from apps.fhir_integration.services import FHIRClientService, FHIRMapper

        connection = FHIRConnection.objects.select_related('patient').get(id=connection_id)
        connection.sync_status = 'SYNCING'
        connection.save(update_fields=['sync_status'])

        payload = HandoverPayload(
            patient_id=str(connection.patient_id),
            data={'connection_id': connection_id},
        )
        orchestrator.broadcast(FHIR_AGENT, ExtAgentEvent.FHIR_SYNC_STARTED, payload)

        try:
            resources = FHIRClientService(connection).fetch_medication_requests()
        except Exception as e:
            connection.sync_status = 'FAILED'
            connection.save(update_fields=['sync_status', 'updated_at'])
            orchestrator.broadcast(FHIR_AGENT, ExtAgentEvent.FHIR_SYNC_FAILED,
                HandoverPayload(patient_id=str(connection.patient_id),
                                data={'error': str(e)}))
            return {'status': 'failed', 'error': str(e)}

        imported, duplicates, rejected = [], [], []
        imported_prescription_ids = []

        with transaction.atomic():
            for resource in resources:
                external_id = resource['id']
                log, created = FHIRImportLog.objects.get_or_create(
                    connection=connection, external_id=external_id,
                    defaults={
                        'resource_type': 'MedicationRequest',
                        'raw_payload'  : resource,
                        'import_status': 'IMPORTED',
                    }
                )
                if not created:
                    duplicates.append(external_id)
                    continue

                try:
                    prescription = FHIRMapper.to_prescription(resource, connection.patient)
                    log.created_prescription = prescription
                    log.save(update_fields=['created_prescription', 'updated_at'])
                    imported.append(external_id)
                    imported_prescription_ids.append(str(prescription.id))
                except Exception as e:
                    log.import_status = 'REJECTED'
                    log.rejection_reason = str(e)
                    log.save(update_fields=['import_status', 'rejection_reason', 'updated_at'])
                    rejected.append(external_id)

        connection.sync_status = 'SUCCESS'
        connection.last_synced_at = timezone.now()
        connection.save(update_fields=['sync_status', 'last_synced_at', 'updated_at'])

        if imported_prescription_ids:
            orchestrator.broadcast(FHIR_AGENT, ExtAgentEvent.FHIR_PRESCRIPTIONS_IMPORTED,
                HandoverPayload(
                    patient_id = str(connection.patient_id),
                    data       = {'prescription_ids': imported_prescription_ids},
                    trace_id   = payload.trace_id,
                ))

        return {
            'imported'  : len(imported),
            'duplicates': len(duplicates),
            'rejected'  : len(rejected),
        }


# ═══════════════════════════════════════════════════════════════════
# EXT-12. VITALS AGENT  (Phase 19)
# ═══════════════════════════════════════════════════════════════════

class VitalsAgent(BaseAgent):
    """
    Owns: vital sign recording, target checking, out-of-range detection.

    Handover In:
        ← Patient API : POST /vitals/ → log_vital
    Handover Out:
        → DoctorAgent        : VITAL_OUT_OF_RANGE
        → NotificationAgent  : patient alert
        → AuditAgent         : PHI access log
    """
    agent_name = VITALS_AGENT

    def log_vital(self, patient_id: str, vital_type: str, value: float,
                  unit: str, source: str, recorded_at: datetime = None,
                  prescription_id: str = None) -> dict:
        from apps.vitals.models import VitalReading, VitalTarget

        reading = VitalReading.objects.create(
            patient_id     = patient_id,
            vital_type     = vital_type,
            value          = value,
            unit           = unit,
            source         = source,
            recorded_at    = recorded_at or timezone.now(),
            prescription_id= prescription_id,
        )
        payload = HandoverPayload(
            patient_id = patient_id,
            data       = {'vital_type': vital_type, 'value': value, 'unit': unit},
        )
        orchestrator.broadcast(VITALS_AGENT, ExtAgentEvent.VITAL_LOGGED, payload)

        # Check against target
        try:
            target = VitalTarget.objects.get(patient_id=patient_id, vital_type=vital_type)
            oor = False
            if target.target_max and value > float(target.target_max):
                oor = True
            if target.target_min and value < float(target.target_min):
                oor = True
            if oor:
                oor_payload = HandoverPayload(
                    patient_id = patient_id,
                    data       = {
                        'vital_type': vital_type,
                        'value'     : value,
                        'unit'      : unit,
                        'target_min': str(target.target_min),
                        'target_max': str(target.target_max),
                    },
                )
                orchestrator.broadcast(VITALS_AGENT, ExtAgentEvent.VITAL_OUT_OF_RANGE, oor_payload)
        except VitalTarget.DoesNotExist:
            pass

        return {'reading_id': str(reading.id)}


# ═══════════════════════════════════════════════════════════════════
# EXT-13. GAMIFICATION AGENT  (Phase 20)
# ═══════════════════════════════════════════════════════════════════

class GamificationAgent(BaseAgent):
    """
    Owns: streaks, badges, weekly adherence scores.
    Triggered by dose events — purely reactive, no side effects.
    Fails silently (never block dose logging).

    Handover In:
        ← AdherenceAgent : DOSE_LOGGED → on_dose_logged
        ← PharmacyAgent  : REFILL_ORDER_DELIVERED → award_refill_proactive_badge
        ← WhatsAppAgent  : WHATSAPP_ONBOARDING_DONE → award_onboarding_badge
        ← ABHAAgent      : ABHA_LINKED → award_abha_linked_badge

    Handover Out:
        → NotificationAgent : streak/badge/milestone notifications
    """
    agent_name = GAMIFICATION_AGENT

    STREAK_MILESTONES = [7, 14, 30, 60, 90, 180, 365]  # days

    def on_dose_logged(self, payload: HandoverPayload) -> dict:
        """Main hook — called on every DOSE_LOGGED event."""
        try:
            status = payload.data.get('status', 'TAKEN')
            patient_id = payload.patient_id
            if not patient_id:
                return {}

            if status == 'TAKEN':
                self._update_streak(patient_id, payload)
            elif status == 'MISSED':
                self._break_streak_if_all_missed_today(patient_id, payload)
        except Exception as e:
            # Gamification NEVER blocks the adherence flow
            logger.warning(f'GamificationAgent silently failed: {e}')
        return {}

    def _update_streak(self, patient_id: str, payload: HandoverPayload):
        from apps.gamification.models import Streak
        from django.utils.timezone import localdate

        streak, _ = Streak.objects.get_or_create(patient_id=patient_id)
        today = localdate()

        if streak.last_dose_date == today:
            return  # Already counted today
        if streak.last_dose_date and (today - streak.last_dose_date).days > 1:
            # Gap in streak — broken
            streak.last_broken_at = timezone.now()
            streak.current_days   = 1
        else:
            streak.current_days += 1

        streak.last_dose_date = today
        if streak.current_days > streak.longest_days:
            streak.longest_days = streak.current_days
        streak.save(update_fields=['current_days', 'longest_days',
                                    'last_dose_date', 'last_broken_at', 'updated_at'])

        # Check milestones
        if streak.current_days in self.STREAK_MILESTONES:
            orchestrator.broadcast(
                GAMIFICATION_AGENT, ExtAgentEvent.STREAK_ACHIEVED,
                HandoverPayload(patient_id=patient_id,
                                data={'streak_days': streak.current_days}),
            )
            self._award_badge(patient_id, f'{streak.current_days}_DAY_STREAK', payload)

    def _break_streak_if_all_missed_today(self, patient_id: str, payload: HandoverPayload):
        from apps.gamification.models import Streak
        from apps.telemetry.models import AdherenceEvent
        from django.utils.timezone import localdate

        today = localdate()
        taken_today = AdherenceEvent.objects.filter(
            patient_id=patient_id,
            scheduled_at__date=today,
            status='TAKEN',
        ).exists()

        if not taken_today:
            Streak.objects.filter(patient_id=patient_id).update(
                last_broken_at=timezone.now(),
                current_days=0,
            )
            orchestrator.broadcast(
                GAMIFICATION_AGENT, ExtAgentEvent.STREAK_BROKEN,
                HandoverPayload(patient_id=patient_id),
            )

    def _award_badge(self, patient_id: str, badge_type: str, payload: HandoverPayload):
        if not patient_id:
            # Event fired for a non-patient account (e.g. a caregiver) — badges
            # are patient-scoped, so there's nothing to award.
            return
        from apps.gamification.models import Badge
        _, created = Badge.objects.get_or_create(
            patient_id=patient_id, badge_type=badge_type
        )
        if created:
            orchestrator.broadcast(
                GAMIFICATION_AGENT, ExtAgentEvent.BADGE_EARNED,
                HandoverPayload(patient_id=patient_id,
                                data={'badge_type': badge_type},
                                trace_id=payload.trace_id),
            )

    def award_refill_proactive_badge(self, payload: HandoverPayload) -> dict:
        self._award_badge(payload.patient_id, BADGE_REFILL_PROACTIVE, payload)
        return {}

    def award_onboarding_badge(self, payload: HandoverPayload) -> dict:
        self._award_badge(payload.patient_id, 'WHATSAPP_ONBOARDED', payload)
        return {}

    def award_abha_linked_badge(self, payload: HandoverPayload) -> dict:
        self._award_badge(payload.patient_id, BADGE_ABHA_LINKED, payload)
        return {}

    def award_digital_rx_badge(self, payload: HandoverPayload) -> dict:
        self._award_badge(payload.patient_id, BADGE_DIGITAL_RX, payload)
        return {}

    def compute_weekly_score(self, patient_id: str, week_start) -> dict:
        """Called by Celery Beat every Monday morning."""
        from apps.gamification.models import WeeklyAdherenceScore
        from apps.telemetry.models import AdherenceEvent
        from datetime import timedelta

        week_end = week_start + timedelta(days=7)
        events = AdherenceEvent.objects.filter(
            patient_id   = patient_id,
            scheduled_at__date__gte=week_start,
            scheduled_at__date__lt =week_end,
        )
        total  = events.count()
        taken  = events.filter(status='TAKEN').count()
        missed = events.filter(status='MISSED').count()
        score  = int((taken / total) * 100) if total > 0 else 0

        weekly_score, _ = WeeklyAdherenceScore.objects.update_or_create(
            patient_id=patient_id, week_start=week_start,
            defaults={'score': score, 'total_doses': total,
                      'taken_doses': taken, 'missed_doses': missed},
        )
        orchestrator.broadcast(
            GAMIFICATION_AGENT, ExtAgentEvent.WEEKLY_SCORE_COMPUTED,
            HandoverPayload(patient_id=patient_id,
                            data={'score': score, 'week_start': str(week_start)}),
        )
        return {'score': score, 'total': total, 'taken': taken}

    def update_adherence_score_snapshot(self, payload: HandoverPayload) -> dict:
        """Called on MILESTONE_REACHED — triggers InsuranceReportsAgent snapshot."""
        return {}


# ═══════════════════════════════════════════════════════════════════
# EXT-14. PHARMACOVIGILANCE AGENT  (Phase 21)
# ═══════════════════════════════════════════════════════════════════

class PharmacovigAgent(BaseAgent):
    """
    Owns: side effect reports, severity assessment, CDSCO report aggregation.

    Handover In:
        ← Patient API : POST /side-effects/ → record_and_assess
    Handover Out:
        → DoctorAgent        : SEVERE_SIDE_EFFECT_DETECTED
        → NotificationAgent  : patient + doctor alerts
        → AuditAgent         : all reports
    """
    agent_name = PHARMACOVIG_AGENT

    def record_and_assess(self, payload: HandoverPayload) -> dict:
        from apps.pharmacovigilance.models import SideEffectReport

        report_id = payload.data.get('report_id')
        report = SideEffectReport.objects.select_related(
            'prescription__medication', 'patient'
        ).get(id=report_id)

        is_severe = report.severity in ('SEVERE', 'LIFE_THREATENING')

        if is_severe:
            orchestrator.broadcast(
                PHARMACOVIG_AGENT,
                ExtAgentEvent.SEVERE_SIDE_EFFECT_DETECTED,
                HandoverPayload(
                    patient_id     = str(report.patient_id),
                    prescription_id= str(report.prescription_id),
                    data           = {
                        'report_id': str(report.id),
                        'symptom'  : report.symptom,
                        'severity' : report.severity,
                        'drug_name': report.prescription.medication.name,
                    },
                    trace_id = payload.trace_id,
                ),
            )
        return {'report_id': str(report.id), 'is_severe': is_severe}

    def flag_for_cdsco_report(self, payload: HandoverPayload) -> dict:
        """Mark severe reports for CDSCO export batch."""
        from apps.pharmacovigilance.models import SideEffectReport
        SideEffectReport.objects.filter(
            id=payload.data.get('report_id')
        ).update(reported_to_cdsco=False)  # Queued for next export
        return {'status': 'flagged_for_cdsco'}

    def generate_cdsco_export(self, from_date, to_date) -> dict:
        """
        Admin-triggered CDSCO export.
        Returns anonymized aggregate in CDSCO VigiBase format.
        """
        from apps.pharmacovigilance.models import SideEffectReport
        from apps.pharmacovigilance.exporters import CDSCOExporter

        reports = SideEffectReport.objects.filter(
            created_at__date__gte=from_date,
            created_at__date__lte=to_date,
            reported_to_cdsco=False,
        ).select_related('prescription__medication')

        export_path = CDSCOExporter(reports).export()
        SideEffectReport.objects.filter(
            id__in=reports.values_list('id', flat=True)
        ).update(reported_to_cdsco=True)
        return {'file_path': export_path, 'records': reports.count()}


# ═══════════════════════════════════════════════════════════════════
# EXT-15. INSURANCE REPORTS AGENT  (Phase 24)
# ═══════════════════════════════════════════════════════════════════

class InsuranceReportsAgent(BaseAgent):
    """
    Owns: time-limited shareable adherence report links.
    Patient controls: creates, revokes, views access logs.
    Third party (insurance) accesses via token — no auth required.

    Handover In:
        ← Patient API     : POST /reports/shares/
        ← GamificationAgent: MILESTONE_REACHED → update_adherence_score_snapshot

    Handover Out:
        → NotificationAgent : REPORT_SHARE_CREATED, REPORT_ACCESSED
        → AuditAgent        : every report access (PHI)
    """
    agent_name = INSURANCE_RPT_AGENT

    DEFAULT_EXPIRY_DAYS = 30

    def create_share(self, patient_id: str, recipient_type: str,
                     recipient_name: str, scope: dict,
                     expiry_days: int = None) -> dict:
        from apps.insurance_reports.models import AdherenceReportShare

        token = str(uuid.uuid4())
        expiry = timezone.now() + timedelta(days=expiry_days or self.DEFAULT_EXPIRY_DAYS)
        share = AdherenceReportShare.objects.create(
            patient_id     = patient_id,
            recipient_type = recipient_type,
            recipient_name = recipient_name,
            access_token   = token,
            expires_at     = expiry,
            data_scope     = scope,
        )
        payload = HandoverPayload(
            patient_id = patient_id,
            data       = {
                'share_id'      : str(share.id),
                'recipient_name': recipient_name,
                'expires_at'    : expiry.isoformat(),
                'public_url'    : f'/api/v1/reports/public/{token}/',
            },
        )
        orchestrator.broadcast(INSURANCE_RPT_AGENT, ExtAgentEvent.REPORT_SHARE_CREATED, payload)
        return {'share_id': str(share.id), 'token': token, 'expires_at': expiry.isoformat()}

    def access_report(self, token: str, accessor_ip: str, accessor_ua: str) -> dict:
        from apps.insurance_reports.models import AdherenceReportShare, ReportAccessLog
        from apps.insurance_reports.services import AdherenceReportBuilder

        share = AdherenceReportShare.objects.select_related('patient').get(
            access_token=token, is_revoked=False
        )
        if share.expires_at < timezone.now():
            return {'error': 'EXPIRED'}

        ReportAccessLog.objects.create(
            share=share, accessor_ip=accessor_ip, accessor_ua=accessor_ua
        )
        share.access_count += 1
        share.save(update_fields=['access_count', 'updated_at'])

        orchestrator.broadcast(
            INSURANCE_RPT_AGENT, ExtAgentEvent.REPORT_ACCESSED,
            HandoverPayload(
                patient_id = str(share.patient_id),
                data       = {'share_id': str(share.id), 'recipient_type': share.recipient_type},
            ),
        )
        report_data = AdherenceReportBuilder(share).build()
        return {'report': report_data}

    def update_adherence_score_snapshot(self, payload: HandoverPayload) -> dict:
        """
        Called when MILESTONE_REACHED — update any live insurance share
        snapshots so the next access has fresh data.
        (Async: delegate to Celery, don't block milestone notification)
        """
        refresh_insurance_report_cache.delay(payload.patient_id)
        return {}

    def revoke_share(self, share_id: str, patient_id: str) -> dict:
        from apps.insurance_reports.models import AdherenceReportShare
        updated = AdherenceReportShare.objects.filter(
            id=share_id, patient_id=patient_id
        ).update(is_revoked=True)
        orchestrator.broadcast(
            INSURANCE_RPT_AGENT, ExtAgentEvent.REPORT_REVOKED,
            HandoverPayload(patient_id=patient_id, data={'share_id': share_id}),
        )
        return {'revoked': bool(updated)}


# ═══════════════════════════════════════════════════════════════════
# EXT-16. GEOFENCE AGENT  (Phase 26)
# ═══════════════════════════════════════════════════════════════════

class GeofenceAgent(BaseAgent):
    """
    Owns: geofence zone management, exit/entry event processing,
          pending dose reminder triggers on exit.

    Location processing is LOCAL on device.
    Device sends zone_id + event_type to backend on exit/entry.
    Coordinates stored only for zone setup — NOT for real-time tracking.

    Handover In:
        ← Mobile App : POST /geofence/event/ → evaluate_pending_doses_on_exit

    Handover Out:
        → NotificationAgent : GEOFENCE_REMINDER_TRIGGERED
        → AuditAgent        : geofence events (privacy-first, no coordinates logged)
    """
    agent_name = GEOFENCE_AGENT

    def evaluate_pending_doses_on_exit(self, payload: HandoverPayload) -> dict:
        """
        On HOME zone exit: check if any doses are due in next 4 hours.
        If yes, send a context-aware reminder.
        """
        from apps.geofence.models import GeofenceZone, GeofenceEvent
        from apps.telemetry.models import ReminderJob

        zone_id    = payload.data.get('zone_id')
        event_type = payload.data.get('event_type', 'EXIT')

        if event_type != 'EXIT':
            return {'status': 'entry_ignored'}

        zone = GeofenceZone.objects.get(id=zone_id, patient_id=payload.patient_id)

        # Record geofence event (no coordinates — privacy first)
        geo_event = GeofenceEvent.objects.create(
            patient_id  = payload.patient_id,
            zone        = zone,
            event_type  = 'EXIT',
            triggered_at= timezone.now(),
        )

        # Find pending doses in next 4 hours
        now        = timezone.now()
        window_end = now + timedelta(hours=4)
        pending_reminders = ReminderJob.objects.filter(
            schedule__prescription__patient_id=payload.patient_id,
            status='PENDING',
            scheduled_at__gte=now,
            scheduled_at__lte=window_end,
        ).select_related('schedule__prescription__medication')

        sent_ids = []
        for reminder in pending_reminders:
            med_name = reminder.schedule.prescription.medication.name
            reminder_payload = HandoverPayload(
                patient_id  = payload.patient_id,
                reminder_id = str(reminder.id),
                data        = {
                    'message_type' : 'GEOFENCE_REMINDER',
                    'med_name'     : med_name,
                    'dose_time'    : reminder.scheduled_at.strftime('%I:%M %p'),
                    'zone_label'   : zone.label,
                },
                trace_id = payload.trace_id,
            )
            orchestrator.handover(
                GEOFENCE_AGENT, NOTIFICATION_EXT,
                ExtAgentEvent.GEOFENCE_REMINDER_TRIGGERED, reminder_payload,
            )
            sent_ids.append(str(reminder.id))

        geo_event.reminders_sent = sent_ids
        geo_event.save(update_fields=['reminders_sent'])

        return {'reminders_triggered': len(sent_ids), 'zone': zone.label}


# ═══════════════════════════════════════════════════════════════════
# EXT-17. ABHA AGENT  (Phase 27)
# ═══════════════════════════════════════════════════════════════════

class ABHAAgent(BaseAgent):
    """
    Owns: ABHA (Ayushman Bharat Health Account) ID linking,
          ABDM health locker prescription import.

    Flow:
        1. Patient provides 14-digit ABHA number
        2. ABDM sends OTP to registered mobile
        3. Patient verifies OTP → access token issued
        4. Sync health records (MedicationRequest resources)

    Handover In:
        ← Patient API : POST /abha/connect/verify-otp/ → finalize_linking
        ← Celery Beat : periodic ABHA sync

    Handover Out:
        → DrugInteractionAgent : ABHA_PRESCRIPTIONS_IMPORTED
        → GamificationAgent    : ABHA_LINKED → award badge
        → AuditAgent           : every ABHA action
    """
    agent_name = ABHA_AGENT

    def initiate_linking(self, patient_id: str, abha_id: str) -> dict:
        """Step 1: Validate ABHA number format and request OTP from ABDM."""
        from apps.abha.services import ABDMGatewayService

        abha_id_clean = abha_id.replace('-', '').replace(' ', '')
        if len(abha_id_clean) != 14 or not abha_id_clean.isdigit():
            return {'error': 'INVALID_ABHA_FORMAT'}

        txn_id = ABDMGatewayService.request_otp(abha_id_clean)
        # Store txn_id in cache for OTP verification step
        from django.core.cache import cache as django_cache
        django_cache.set(f'abha_link:{patient_id}', {
            'abha_id': abha_id_clean, 'txn_id': txn_id
        }, timeout=300)  # 5 min OTP window
        return {'status': 'otp_sent', 'txn_id': txn_id}

    def finalize_linking(self, patient_id: str, otp: str) -> dict:
        """Step 2: Verify OTP, get access token, create ABHAConnection."""
        from django.core.cache import cache as django_cache
        from apps.abha.services import ABDMGatewayService
        from apps.abha.models import ABHAConnection

        ctx = django_cache.get(f'abha_link:{patient_id}')
        if not ctx:
            return {'error': 'OTP_EXPIRED'}

        try:
            access_token, abha_address = ABDMGatewayService.verify_otp(
                ctx['txn_id'], otp, ctx['abha_id']
            )
        except Exception:
            return {'error': 'OTP_INVALID'}

        connection, created = ABHAConnection.objects.update_or_create(
            patient_id=patient_id,
            defaults={
                'abha_id'          : ctx['abha_id'],
                'abha_address'     : abha_address,
                'consent_token_enc': access_token,  # Encrypted at rest
                'linked_at'        : timezone.now(),
            },
        )
        django_cache.delete(f'abha_link:{patient_id}')

        # Trigger async sync
        sync_abha_records.delay(str(connection.id))

        payload = HandoverPayload(patient_id=patient_id,
                                   data={'abha_id': ctx['abha_id']})
        orchestrator.broadcast(ABHA_AGENT, ExtAgentEvent.ABHA_LINKED, payload)
        return {'status': 'linked', 'abha_id': ctx['abha_id']}

    def sync_health_records(self, connection_id: str) -> dict:
        """Pull MedicationRequest resources from ABDM health locker."""
        from apps.abha.models import ABHAConnection, ABHAImportLog
        from apps.abha.services import ABDMGatewayService, ABHAFHIRMapper

        connection = ABHAConnection.objects.select_related('patient').get(id=connection_id)
        resources = ABDMGatewayService.fetch_records(
            connection.abha_id, connection.consent_token_enc, 'MedicationRequest'
        )
        imported_ids = []

        with transaction.atomic():
            for resource in resources:
                external_id = resource.get('id')
                log, created = ABHAImportLog.objects.get_or_create(
                    connection=connection, record_type='Prescription',
                    defaults={'raw_fhir_payload': resource,
                              'import_status': 'IMPORTED',
                              'source_hospital': resource.get('encounter', {}).get('hospital')},
                )
                if not created:
                    log.import_status = 'DUPLICATE'
                    log.save(update_fields=['import_status'])
                    continue

                try:
                    prescription = ABHAFHIRMapper.to_prescription(resource, connection.patient)
                    log.created_prescription = prescription
                    log.save(update_fields=['created_prescription', 'updated_at'])
                    imported_ids.append(str(prescription.id))
                except Exception as e:
                    log.import_status = 'REJECTED'
                    log.save(update_fields=['import_status', 'updated_at'])

        connection.last_synced_at = timezone.now()
        connection.save(update_fields=['last_synced_at', 'updated_at'])

        if imported_ids:
            orchestrator.broadcast(
                ABHA_AGENT, ExtAgentEvent.ABHA_PRESCRIPTIONS_IMPORTED,
                HandoverPayload(
                    patient_id=str(connection.patient_id),
                    data={'prescription_ids': imported_ids},
                ),
            )
        return {'imported': len(imported_ids)}


# ═══════════════════════════════════════════════════════════════════
# EXT-18. TENANT AGENT  (Phase 28 — Scale Layer)
# ═══════════════════════════════════════════════════════════════════

class TenantAgent(BaseAgent):
    """
    Owns: multi-tenant creation, tenant plan management.
    Uses PostgreSQL Row-Level Security for data isolation.
    TenantMiddleware sets search_path + app.tenant_id on every request.

    This is a SCALE layer agent — not needed for MVP.

    Handover In:
        ← SUPER_ADMIN API : POST /admin/api/v1/tenants/
    Handover Out:
        → NotificationAgent : tenant onboarding
        → AuditAgent        : all tenant actions
    """
    agent_name = TENANT_AGENT

    def create_tenant(self, name: str, subdomain: str, plan: str,
                      admin_user_id: str) -> dict:
        from apps.tenants.models import Tenant, TenantAdmin
        from apps.tenants.provisioner import TenantProvisioner

        with transaction.atomic():
            tenant = Tenant.objects.create(
                name=name, subdomain=subdomain, plan=plan,
                max_patients=self._max_patients_for_plan(plan),
            )
            TenantAdmin.objects.create(
                tenant=tenant, user_id=admin_user_id, is_primary=True
            )
            # Apply RLS policies for this tenant
            TenantProvisioner(tenant).apply_rls_policies()

        payload = HandoverPayload(
            user_id = admin_user_id,
            data    = {'tenant_id': str(tenant.id), 'subdomain': subdomain},
        )
        orchestrator.broadcast(TENANT_AGENT, ExtAgentEvent.TENANT_CREATED, payload)
        return {'tenant_id': str(tenant.id), 'subdomain': subdomain}

    @staticmethod
    def _max_patients_for_plan(plan: str) -> int:
        return {'CLINIC': 500, 'HOSPITAL': 5000, 'ENTERPRISE': 999999}.get(plan, 500)


# ═══════════════════════════════════════════════════════════════════
# EXT-19. NEW CELERY TASKS
# ═══════════════════════════════════════════════════════════════════
# call_pharmacy_api lives in apps/pharmacy/tasks.py (the actually
# Celery-registered version) — PharmacyAgent no longer calls a same-module
# copy of it now that refill ordering goes through the agentic
# apps.agent_runtime.services.pharmacy_pipeline / create_refill_order tool.


@shared_task
def check_refill_thresholds():
    """
    Daily Celery Beat — check all active prescriptions for refill threshold.
    Replaces existing check_refill_alerts task (extend it with this logic).
    """
    from apps.clinical.models import Prescription

    low_stock = Prescription.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        remaining_quantity__lte=models.F('refill_alert_days'),
    ).select_related('patient')

    for rx in low_stock:
        payload = HandoverPayload(
            patient_id     = str(rx.patient_id),
            prescription_id= str(rx.id),
            data           = {'remaining_quantity': rx.remaining_quantity},
        )
        orchestrator.broadcast('ClinicalApp', ExtAgentEvent.REFILL_THRESHOLD_REACHED, payload)
    return {'prescriptions_checked': low_stock.count()}


@shared_task
def sync_all_fhir_connections():
    """Daily sync — all FHIR-connected patients."""
    from apps.fhir_integration.models import FHIRConnection
    connections = FHIRConnection.objects.filter(
        sync_status__in=['IDLE', 'SUCCESS'],
        deleted_at__isnull=True,
    ).values_list('id', flat=True)
    for conn_id in connections:
        sync_single_fhir_connection.delay(str(conn_id))
    return {'connections_queued': len(connections)}


@shared_task(bind=True, max_retries=2)
def sync_single_fhir_connection(self, connection_id: str):
    fhir_agent = AgentRegistry.get(FHIR_AGENT)
    try:
        return fhir_agent.sync_connection(connection_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@shared_task
def sync_all_abha_connections():
    """Daily ABHA sync — all linked patients."""
    from apps.abha.models import ABHAConnection
    connections = ABHAConnection.objects.filter(deleted_at__isnull=True)
    for conn in connections:
        sync_abha_records.delay(str(conn.id))
    return {'connections_queued': connections.count()}


@shared_task(bind=True, max_retries=2)
def sync_abha_records(self, connection_id: str):
    abha_agent = AgentRegistry.get(ABHA_AGENT)
    try:
        return abha_agent.sync_health_records(connection_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@shared_task
def compute_weekly_scores_all_patients():
    """
    Every Monday 6 AM UTC — compute adherence scores for all active patients.
    """
    from apps.clinical.models import Patient
    from datetime import date, timedelta

    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)  # Previous week

    patients = Patient.objects.filter(
        deleted_at__isnull=True,
        user__subscription__status='ACTIVE',
    ).values_list('id', flat=True)

    gamification_agent = AgentRegistry.get(GAMIFICATION_AGENT)
    for pid in patients:
        try:
            gamification_agent.compute_weekly_score(str(pid), last_monday)
        except Exception as e:
            logger.warning(f'Weekly score failed for {pid}: {e}')
    return {'patients_processed': len(patients)}


@shared_task
def expire_insurance_report_shares():
    """Daily — mark expired report shares."""
    from apps.insurance_reports.models import AdherenceReportShare
    expired = AdherenceReportShare.objects.filter(
        expires_at__lt=timezone.now(),
        is_revoked=False,
    ).update(is_revoked=True)
    return {'expired_shares': expired}


@shared_task
def refresh_insurance_report_cache(patient_id: str):
    """Async refresh of report data cache after milestone."""
    from django.core.cache import cache as django_cache
    cache_key = f'insurance_report:{patient_id}'
    django_cache.delete(cache_key)
    return {'status': 'cache_cleared'}


@shared_task
def cleanup_expired_telegram_sessions():
    """
    Every hour — set idle sessions back to IDLE if inactive > 30 min.
    Prevents stale AWAITING_DOSE_RESPONSE / AWAITING_OTP states.
    """
    from apps.telegram_bot.models import TelegramSession
    stale_cutoff = timezone.now() - timedelta(minutes=30)
    TelegramSession.objects.filter(
        state__in=['AWAITING_DOSE_RESPONSE', 'AWAITING_OTP', 'AWAITING_CONTACT'],
        last_activity_at__lt=stale_cutoff,
    ).update(state='IDLE', state_data={})
    return {'status': 'cleaned'}


@shared_task(bind=True, max_retries=3)
def initiate_ivr_call(self, patient_id: str, reminder_job_id: str, phone_number: str):
    """
    Triggered by ReminderAgent escalation when patient has voice_call enabled.
    Uses Twilio Voice API to initiate outbound IVR call.
    """
    from apps.notifications.services import TwilioVoiceService
    from apps.telemetry.models import IVRCallLog

    try:
        call_sid = TwilioVoiceService.initiate_call(
            to=phone_number,
            twiml_url=f'/api/v1/ivr/twiml/{reminder_job_id}/',
            status_callback=f'/api/v1/ivr/webhook/status/',
        )
        IVRCallLog.objects.create(
            patient_id=patient_id,
            reminder_job_id=reminder_job_id,
            twilio_call_sid=call_sid,
            phone_number=phone_number,
            status='INITIATED',
        )
        return {'call_sid': call_sid}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task
def export_cdsco_monthly_report():
    """
    First day of each month — generate CDSCO pharmacovigilance export.
    """
    from datetime import date
    from dateutil.relativedelta import relativedelta
    pharmacovig_agent = AgentRegistry.get(PHARMACOVIG_AGENT)
    today       = date.today()
    from_date   = (today - relativedelta(months=1)).replace(day=1)
    to_date     = today.replace(day=1)
    return pharmacovig_agent.generate_cdsco_export(from_date, to_date)


# ═══════════════════════════════════════════════════════════════════
# EXT-20. EXTENDED CELERY BEAT SCHEDULE
# Merge this with MEDADHERE_CELERY_BEAT_SCHEDULE in agenthandover.py
# ═══════════════════════════════════════════════════════════════════

from celery.schedules import crontab

MEDADHERE_EXTENSION_BEAT_SCHEDULE = {
    # Pharmacy
    'refill-threshold-check': {
        'task'    : 'medadhere_extensions_handover.check_refill_thresholds',
        'schedule': crontab(hour=9, minute=0),           # 9:00 AM UTC daily (replaces old refill task)
    },
    # FHIR
    'fhir-daily-sync': {
        'task'    : 'medadhere_extensions_handover.sync_all_fhir_connections',
        'schedule': crontab(hour=3, minute=0),           # 3:00 AM UTC daily
    },
    # ABHA
    'abha-daily-sync': {
        'task'    : 'medadhere_extensions_handover.sync_all_abha_connections',
        'schedule': crontab(hour=4, minute=0),           # 4:00 AM UTC daily
    },
    # Gamification
    'weekly-adherence-scores': {
        'task'    : 'medadhere_extensions_handover.compute_weekly_scores_all_patients',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),           # Monday 6:00 AM UTC
    },
    # Insurance Reports
    'expire-report-shares': {
        'task'    : 'medadhere_extensions_handover.expire_insurance_report_shares',
        'schedule': crontab(hour=0, minute=0),           # Midnight UTC daily
    },
    # Telegram
    'cleanup-telegram-sessions': {
        'task'    : 'medadhere_extensions_handover.cleanup_expired_telegram_sessions',
        'schedule': crontab(minute='*/30'),        # Every 30 minutes
    },
    # Pharmacovigilance
    'cdsco-monthly-export': {
        'task'    : 'medadhere_extensions_handover.export_cdsco_monthly_report',
        'schedule': crontab(hour=6, minute=0, day_of_month=1),           # 1st of each month, 6 AM UTC
    },
}


# ═══════════════════════════════════════════════════════════════════
# EXT-21. NEW MANAGEMENT COMMANDS
# ═══════════════════════════════════════════════════════════════════

"""
Add to apps/*/management/commands/:

python manage.py seed_pharmacy_partners
    → Creates PharmEasy, 1mg, Netmeds records (test API keys)
    → Seeds with supported_states and avg_delivery_hrs

python manage.py seed_whatsapp_templates
    → Loads all multi-language WhatsApp message templates into DB
    → Languages: en, hi, mr, ta, te, bn, gu, kn, ml, pa, ur

python manage.py sync_openfda_interactions --batch-size 1000
    → Pulls drug-drug interaction data from OpenFDA into DrugInteraction table
    → Use for pre-seeding local cache (reduces live API calls)

python manage.py generate_abha_test_data
    → Creates test ABHA numbers and mock ABDM responses for testing

python manage.py export_cdsco_report --from 2024-01-01 --to 2024-12-31
    → Manual CDSCO export for a date range

python manage.py create_tenant --name "Apollo Indore" --subdomain apollo-indore \
    --plan HOSPITAL --admin-email admin@apollo.com
    → Creates tenant + admin user + applies RLS policies

python manage.py check_fhir_connections
    → Health check all FHIR connections, report stale/broken ones
"""


# ═══════════════════════════════════════════════════════════════════
# EXT-22. NEW DB INDEXES
# ═══════════════════════════════════════════════════════════════════

"""
-- Pharmacy
CREATE INDEX idx_refill_orders_prescription_status
    ON pharmacy.refill_orders(prescription_id, status)
    WHERE deleted_at IS NULL;

-- Doctor portal
CREATE INDEX idx_doctor_patient_links_patient
    ON doctor_portal.doctor_patient_links(patient_id, can_receive_alerts)
    WHERE deleted_at IS NULL;

-- WhatsApp
CREATE UNIQUE INDEX idx_whatsapp_sessions_phone
    ON whatsapp_bot.whatsapp_sessions(phone_number)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX idx_whatsapp_interaction_msg_id
    ON whatsapp_bot.interaction_logs(whatsapp_msg_id)
    WHERE whatsapp_msg_id IS NOT NULL;

-- Vitals
CREATE INDEX idx_vital_readings_patient_type_time
    ON vitals.vital_readings(patient_id, vital_type, recorded_at DESC)
    WHERE deleted_at IS NULL;

-- Gamification
CREATE UNIQUE INDEX idx_streaks_patient
    ON gamification.streaks(patient_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_weekly_scores_patient_week
    ON gamification.weekly_scores(patient_id, week_start DESC);

-- Side effects
CREATE INDEX idx_side_effects_prescription
    ON pharmacovig.side_effect_reports(prescription_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_side_effects_cdsco_queue
    ON pharmacovig.side_effect_reports(created_at)
    WHERE reported_to_cdsco = FALSE AND severity IN ('SEVERE', 'LIFE_THREATENING');

-- Insurance reports
CREATE UNIQUE INDEX idx_report_shares_token
    ON insurance_reports.report_shares(access_token)
    WHERE is_revoked = FALSE;

-- FHIR / ABHA deduplication
CREATE UNIQUE INDEX idx_fhir_import_connection_external
    ON fhir.fhir_import_logs(connection_id, external_id);

CREATE UNIQUE INDEX idx_abha_import_connection_record
    ON abha.abha_import_logs(connection_id, record_type, id);

-- Geofence
CREATE INDEX idx_geofence_zones_patient_active
    ON geofence.geofence_zones(patient_id)
    WHERE is_active = TRUE AND deleted_at IS NULL;

-- Drug interaction cache invalidation
CREATE INDEX idx_drug_interaction_check_logs_prescription
    ON clinical.drug_interaction_check_logs(prescription_id, checked_at DESC);

-- Multi-tenant RLS
CREATE UNIQUE INDEX idx_tenants_subdomain
    ON tenants.tenants(subdomain)
    WHERE is_active = TRUE;
"""


# ═══════════════════════════════════════════════════════════════════
# EXT-23. NEW REDIS CACHE KEYS
# ═══════════════════════════════════════════════════════════════════

"""
EXISTING KEYS (from agenthandover.py) — keep as-is:
    adherence:today:{patient_id}            TTL: 60s
    risk_score:{patient_id}                 TTL: 1hr
    subscription:{user_id}                  TTL: 5min
    high_risk_patients:{patient_id}         TTL: 1hr

NEW EXTENSION KEYS:

    drug_interaction:{drug_a}:{drug_b}      TTL: 24hr
        → Drug-drug interaction check result (OpenFDA)
        → Key parts alphabetically sorted (order-independent)

    abha_link:{patient_id}                  TTL: 5min
        → ABHA linking OTP context {abha_id, txn_id}

    whatsapp_rate:{phone_number}            TTL: 60s
        → Rate limiting WhatsApp inbound (max 10 messages/min)

    insurance_report:{patient_id}           TTL: 1hr
        → Cached report data for public share access

    family_members:{user_id}               TTL: 5min
        → Cached list of family members for context switcher

    gamification:streak:{patient_id}       TTL: 60s
        → Current streak data (hot path — loaded on every dose log)

    weekly_score:{patient_id}:{week_start} TTL: 7 days
        → Computed weekly adherence score

    fhir_token:{connection_id}             TTL: token_expires_at
        → Decrypted FHIR access token (only in memory, not DB)

    geofence_zones:{patient_id}            TTL: 5min
        → Active geofence zones list (loaded on each geofence event)
"""


# ═══════════════════════════════════════════════════════════════════
# EXT-24. BOOTSTRAP EXTENSION AGENTS
# ═══════════════════════════════════════════════════════════════════

def bootstrap_extension_agents() -> list:
    """
    Call in CoreConfig.ready() AFTER bootstrap_agents() from agenthandover.py.

    # apps/core/apps.py — complete ready() method:
    class CoreConfig(AppConfig):
        name = 'apps.core'

        def ready(self):
            from agenthandover import bootstrap_agents
            from medadhere_extensions_handover import (
                bootstrap_extension_agents,
                register_extension_events,
            )
            # Phase 0-12: core agents
            bootstrap_agents()
            # Phase 13-28: extension agents
            bootstrap_extension_agents()
            # Wire new events into orchestrator
            register_extension_events()
    """
    extension_agents = [
        PharmacyAgent(),
        DoctorAgent(),
        DrugInteractionAgent(),
        FamilyAgent(),
        FHIRAgent(),
        VitalsAgent(),
        GamificationAgent(),
        PharmacovigAgent(),
        InsuranceReportsAgent(),
        GeofenceAgent(),
        ABHAAgent(),
        TenantAgent(),
    ]
    registered = [a.agent_name for a in extension_agents]
    logger.info(f'MedAdhere extension agents bootstrapped: {registered}')
    return registered


# ─── End of medadhere_extensions_handover.py ─────────────────────────────────
"""
QUICK REFERENCE — EXTENSION AGENTS:

    PharmacyAgent       : pharmacy partners, auto-refill orders, delivery tracking
    DoctorAgent         : doctor linking, digital Rx, patient alerts to doctor
    WhatsAppBotAgent    : WhatsApp conversation flow, intent parsing, dose logging
    DrugInteractionAgent: OpenFDA live checks, severe interaction blocking
    FamilyAgent         : family groups, multi-patient account management
    FHIRAgent           : FHIR R4 server sync, MedicationRequest import
    VitalsAgent         : BP/glucose/SpO2 logging, out-of-range detection
    GamificationAgent   : streaks, badges, weekly scores (non-blocking)
    PharmacovigAgent    : side effect reports, CDSCO export
    InsuranceReportsAgent: time-limited shareable adherence report links
    GeofenceAgent       : zone-exit aware dose reminders (privacy-first)
    ABHAAgent           : ABHA ID linking, ABDM health locker sync
    TenantAgent         : multi-tenant provisioning, RLS (scale layer)

AGENT EXTENSION RULE (same as agenthandover.py):
    Agent A → orchestrator.handover/broadcast(A, B, event, payload) → Agent B
    NEVER call extension agents directly from core agents
    ALWAYS go through orchestrator

NEW APP DIRECTORIES TO CREATE:
    apps/pharmacy/
    apps/doctor_portal/
    apps/whatsapp_bot/
    apps/family/
    apps/fhir_integration/
    apps/vitals/
    apps/gamification/
    apps/pharmacovigilance/
    apps/insurance_reports/
    apps/geofence/
    apps/abha/
    apps/tenants/

NEW SCHEMAS TO CREATE (in PostgreSQL):
    pharmacy, doctor_portal, whatsapp_bot, family, fhir,
    vitals, gamification, pharmacovig, insurance_reports,
    geofence, abha, tenants

ADD TO config/db_routers.py SCHEMA_APP_MAP:
    'pharmacy'         : ['pharmacy'],
    'doctor_portal'    : ['doctor_portal'],
    'whatsapp_bot'     : ['whatsapp_bot'],
    'family'           : ['family'],
    'fhir_integration' : ['fhir'],
    'vitals'           : ['vitals'],
    'gamification'     : ['gamification'],
    'pharmacovigilance': ['pharmacovig'],
    'insurance_reports': ['insurance_reports'],
    'geofence'         : ['geofence'],
    'abha'             : ['abha'],
    'tenants'          : ['tenants'],

ADD TO INSTALLED_APPS in config/settings/base.py:
    'apps.pharmacy',
    'apps.doctor_portal',
    'apps.whatsapp_bot',
    'apps.family',
    'apps.fhir_integration',
    'apps.vitals',
    'apps.gamification',
    'apps.pharmacovigilance',
    'apps.insurance_reports',
    'apps.geofence',
    'apps.abha',
    'apps.tenants',

ADD TO requirements.txt:
    fhirclient==4.2.0        # FHIR R4 client
    requests>=2.31.0         # HTTP calls (OpenFDA, ABDM, pharmacy APIs)
    python-dateutil>=2.8     # Date calculations for gamification
    twilio>=8.0.0            # IVR voice (already in core for SMS)

SECURITY: New endpoints requiring special attention:
    POST /api/v1/whatsapp/webhook/     → validate Twilio signature (X-Twilio-Signature)
    POST /api/v1/pharmacy/webhook/*/   → validate HMAC partner signature
    GET  /api/v1/reports/public/{token}/ → no auth, rate limit 100/hr per IP
    POST /api/v1/ivr/webhook/*/        → validate Twilio signature
    POST /api/v1/abha/connect/         → rate limit 3 attempts per patient per hour
"""
