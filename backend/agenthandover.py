"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           MEDADHERE — AGENT HANDOVER SYSTEM                                ║
║           agenthandover.py                                                 ║
║                                                                            ║
║  Purpose: Central orchestration file that coordinates between all backend  ║
║  agents (services), defines inter-service contracts, handover protocols,   ║
║  and the complete event-driven flow of the MedAdhere system.               ║
║                                                                            ║
║  Stack : Django 5.x · DRF · PostgreSQL · Celery + Redis · JWT             ║
║  Author: MedAdhere Backend Team                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

TABLE OF CONTENTS
─────────────────
1.  AgentRegistry            — all agents registered here
2.  HandoverPayload          — typed contract between agents
3.  AgentOrchestrator        — main event router
4.  AuthAgent                — login, register, MFA, sessions
5.  PatientAgent             — patient profile, conditions, onboarding
6.  CaregiverAgent           — caregiver links, permissions, alerts
7.  MedicationAgent          — prescriptions, schedules, generation
8.  ReminderAgent            — reminder dispatch, escalation
9.  AdherenceAgent           — dose logging, rate calculation, streaks
10. NotificationAgent        — multi-channel notification dispatch
11. IoTAgent                 — device linking, event ingestion
12. AIAgent                  — risk scoring, insights, recommendations
13. SubscriptionAgent        — plans, feature gates, billing
14. StoreAgent               — hardware store, orders, unique IDs
15. AdminAgent               — platform-level admin operations
16. AuditAgent               — HIPAA audit trail
17. AgentHandoverProtocols   — inter-agent call contracts
18. BackgroundJobHandover    — Celery task handover registry
19. ErrorBoundaries          — inter-agent failure handling
20. SystemBootstrap          — startup sequence
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import pytz
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('medadhere.agents')


# ═══════════════════════════════════════════════════════════════════
# 1. AGENT REGISTRY
# ═══════════════════════════════════════════════════════════════════

class AgentName(str, Enum):
    AUTH          = 'AuthAgent'
    PATIENT       = 'PatientAgent'
    CAREGIVER     = 'CaregiverAgent'
    MEDICATION    = 'MedicationAgent'
    REMINDER      = 'ReminderAgent'
    ADHERENCE     = 'AdherenceAgent'
    NOTIFICATION  = 'NotificationAgent'
    IOT           = 'IoTAgent'
    AI            = 'AIAgent'
    SUBSCRIPTION  = 'SubscriptionAgent'
    STORE         = 'StoreAgent'
    ADMIN         = 'AdminAgent'
    AUDIT         = 'AuditAgent'


class AgentRegistry:
    """
    Central registry of all backend agents.
    Agents are singleton services — each owns one domain.
    Agents communicate ONLY through HandoverPayload contracts.
    Direct import and call between agents is FORBIDDEN.
    """
    _instances: dict[AgentName, 'BaseAgent'] = {}

    @classmethod
    def register(cls, name: AgentName, agent: 'BaseAgent'):
        cls._instances[name] = agent
        logger.info(f'Agent registered: {name}')

    @classmethod
    def get(cls, name: AgentName) -> 'BaseAgent':
        if name not in cls._instances:
            raise AgentNotFoundError(f'Agent {name} is not registered')
        return cls._instances[name]

    @classmethod
    def all_agents(cls) -> list[AgentName]:
        return list(cls._instances.keys())


# ═══════════════════════════════════════════════════════════════════
# 2. HANDOVER PAYLOAD — Typed Contract Between Agents
# ═══════════════════════════════════════════════════════════════════

@dataclass
class HandoverPayload:
    """
    All inter-agent communication uses this typed contract.
    No agent passes raw dicts or model instances to another agent.

    Pattern:
        result = orchestrator.handover(
            from_agent=AgentName.ADHERENCE,
            to_agent=AgentName.AI,
            event=AgentEvent.DOSE_LOGGED,
            payload=HandoverPayload(
                patient_id=str(patient.id),
                data={'status': 'MISSED', 'prescription_id': '...'}
            )
        )
    """
    patient_id:     Optional[str]  = None
    user_id:        Optional[str]  = None
    prescription_id:Optional[str]  = None
    device_id:      Optional[str]  = None
    reminder_id:    Optional[str]  = None
    subscription_id:Optional[str]  = None
    order_id:       Optional[str]  = None
    data:           dict           = field(default_factory=dict)
    metadata:       dict           = field(default_factory=dict)
    trace_id:       str            = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:     datetime       = field(default_factory=timezone.now)

    def to_log(self) -> dict:
        return {
            'trace_id':   self.trace_id,
            'patient_id': self.patient_id,
            'user_id':    self.user_id,
            'data_keys':  list(self.data.keys()),
        }


@dataclass
class HandoverResult:
    success:  bool
    data:     dict          = field(default_factory=dict)
    error:    Optional[str] = None
    agent:    Optional[str] = None
    trace_id: Optional[str] = None


class AgentEvent(str, Enum):
    """All events that can flow between agents"""
    # Auth events
    USER_REGISTERED          = 'user_registered'
    USER_LOGIN               = 'user_login'
    USER_LOGOUT              = 'user_logout'
    PASSWORD_CHANGED         = 'password_changed'
    MFA_ENABLED              = 'mfa_enabled'

    # Patient events
    PATIENT_ONBOARDED        = 'patient_onboarded'
    PATIENT_PROFILE_UPDATED  = 'patient_profile_updated'
    PATIENT_HOSPITALIZED     = 'patient_hospitalized'
    PATIENT_DISCHARGED       = 'patient_discharged'
    TIMEZONE_CHANGED         = 'timezone_changed'

    # Medication events
    PRESCRIPTION_CREATED     = 'prescription_created'
    PRESCRIPTION_UPDATED     = 'prescription_updated'
    PRESCRIPTION_ENDED       = 'prescription_ended'
    SCHEDULE_CREATED         = 'schedule_created'
    SCHEDULE_UPDATED         = 'schedule_updated'
    SCHEDULE_DEACTIVATED     = 'schedule_deactivated'

    # Adherence events
    DOSE_LOGGED              = 'dose_logged'
    DOSE_CONFIRMED           = 'dose_confirmed'
    DOSE_MISSED              = 'dose_missed'
    DOSE_WINDOW_OPENED       = 'dose_window_opened'
    DOSE_WINDOW_CLOSED       = 'dose_window_closed'

    # Reminder events
    REMINDER_SENT            = 'reminder_sent'
    REMINDER_FAILED          = 'reminder_failed'
    ESCALATION_TRIGGERED     = 'escalation_triggered'
    ESCALATION_RESOLVED      = 'escalation_resolved'

    # IoT events
    DEVICE_LINKED            = 'device_linked'
    DEVICE_UNLINKED          = 'device_unlinked'
    DEVICE_EVENT_RECEIVED    = 'device_event_received'
    DEVICE_OFFLINE           = 'device_offline'
    DEVICE_LOW_BATTERY       = 'device_low_battery'

    # AI events
    RISK_SCORE_UPDATED       = 'risk_score_updated'
    HIGH_RISK_DETECTED       = 'high_risk_detected'
    INSIGHT_GENERATED        = 'insight_generated'

    # Subscription events
    SUBSCRIPTION_CREATED     = 'subscription_created'
    SUBSCRIPTION_UPGRADED    = 'subscription_upgraded'
    SUBSCRIPTION_DOWNGRADED  = 'subscription_downgraded'
    SUBSCRIPTION_EXPIRED     = 'subscription_expired'
    SUBSCRIPTION_CANCELLED   = 'subscription_cancelled'

    # Store events
    ORDER_PLACED             = 'order_placed'
    ORDER_SHIPPED            = 'order_shipped'
    ORDER_DELIVERED          = 'order_delivered'
    DEVICE_ID_ASSIGNED       = 'device_id_assigned'

    # Caregiver events
    CAREGIVER_INVITED        = 'caregiver_invited'
    CAREGIVER_LINKED         = 'caregiver_linked'
    CAREGIVER_UNLINKED       = 'caregiver_unlinked'

    # Admin events
    ADMIN_ACTION             = 'admin_action'
    SYSTEM_ALERT             = 'system_alert'


# ═══════════════════════════════════════════════════════════════════
# 3. AGENT ORCHESTRATOR — Central Event Router
# ═══════════════════════════════════════════════════════════════════

class AgentOrchestrator:
    """
    The single routing layer between all agents.
    No agent calls another agent directly.
    All cross-agent communication goes through orchestrator.handover().

    This enforces:
    - Traceability (every handover has a trace_id)
    - Audit (handovers logged before execution)
    - Error isolation (one agent failure doesn't cascade)
    - Easy testing (mock any agent at the orchestrator level)
    """

    def __init__(self):
        self.registry = AgentRegistry
        self._event_handlers: dict[AgentEvent, list[tuple[AgentName, str]]] = {}
        self._register_event_handlers()

    def _register_event_handlers(self):
        """
        Declare which agents listen to which events.
        Format: event → [(agent_name, method_name), ...]
        """
        self._event_handlers = {
            # ─── Auth ────────────────────────────────────────────────
            AgentEvent.USER_REGISTERED: [
                (AgentName.PATIENT,       'initialize_patient_profile'),
                (AgentName.SUBSCRIPTION,  'assign_free_plan'),
                (AgentName.NOTIFICATION,  'send_welcome_notification'),
                (AgentName.AUDIT,         'log_registration'),
            ],
            AgentEvent.PASSWORD_CHANGED: [
                (AgentName.AUTH,          'revoke_all_sessions'),
                (AgentName.AUDIT,         'log_password_change'),
                (AgentName.NOTIFICATION,  'send_security_alert'),
            ],

            # ─── Prescription / Schedule ─────────────────────────────
            AgentEvent.PRESCRIPTION_CREATED: [
                (AgentName.MEDICATION,    'validate_drug_interactions'),
                (AgentName.REMINDER,      'generate_reminder_schedule'),
                (AgentName.AI,            'update_schedule_complexity_score'),
                (AgentName.AUDIT,         'log_prescription_created'),
            ],
            AgentEvent.SCHEDULE_UPDATED: [
                (AgentName.REMINDER,      'regenerate_future_reminders'),
                (AgentName.AUDIT,         'log_schedule_change'),
            ],
            AgentEvent.SCHEDULE_DEACTIVATED: [
                (AgentName.REMINDER,      'cancel_future_reminders'),
                (AgentName.AUDIT,         'log_schedule_deactivated'),
            ],

            # ─── Adherence ───────────────────────────────────────────
            AgentEvent.DOSE_LOGGED: [
                (AgentName.REMINDER,      'cancel_pending_escalation'),
                (AgentName.AI,            'trigger_realtime_risk_update'),
                (AgentName.CAREGIVER,     'notify_caregivers_if_watched'),
                (AgentName.AUDIT,         'log_dose_event'),
            ],
            AgentEvent.DOSE_MISSED: [
                (AgentName.REMINDER,      'start_escalation_ladder'),
                (AgentName.AI,            'flag_missed_dose_pattern'),
                (AgentName.AUDIT,         'log_missed_dose'),
            ],
            AgentEvent.HIGH_RISK_DETECTED: [
                (AgentName.CAREGIVER,     'send_high_risk_alert_to_caregivers'),
                (AgentName.NOTIFICATION,  'send_patient_risk_notification'),
                (AgentName.ADMIN,         'log_high_risk_event'),
                (AgentName.AUDIT,         'log_risk_alert'),
            ],
            AgentEvent.INSIGHT_GENERATED: [
                (AgentName.NOTIFICATION,  'send_insight_notification'),
            ],

            # ─── IoT ─────────────────────────────────────────────────
            AgentEvent.DEVICE_EVENT_RECEIVED: [
                (AgentName.ADHERENCE,     'log_dose_from_iot'),
                (AgentName.AUDIT,         'log_device_event'),
            ],
            AgentEvent.DEVICE_LINKED: [
                (AgentName.AUDIT,         'log_device_linked'),
                (AgentName.NOTIFICATION,  'send_device_linked_confirmation'),
            ],
            AgentEvent.DEVICE_LOW_BATTERY: [
                (AgentName.NOTIFICATION,  'send_low_battery_alert'),
            ],
            AgentEvent.DEVICE_OFFLINE: [
                (AgentName.NOTIFICATION,  'send_device_offline_alert'),
                (AgentName.ADMIN,         'flag_device_offline'),
            ],

            # ─── Subscription ────────────────────────────────────────
            AgentEvent.SUBSCRIPTION_UPGRADED: [
                (AgentName.NOTIFICATION,  'send_upgrade_confirmation'),
                (AgentName.REMINDER,      'unlock_premium_reminder_channels'),
                (AgentName.AUDIT,         'log_subscription_change'),
            ],
            AgentEvent.SUBSCRIPTION_EXPIRED: [
                (AgentName.REMINDER,      'downgrade_reminder_channels'),
                (AgentName.IOT,           'disable_device_sync'),
                (AgentName.NOTIFICATION,  'send_expiry_notification'),
                (AgentName.AUDIT,         'log_subscription_expiry'),
            ],

            # ─── Store ───────────────────────────────────────────────
            AgentEvent.ORDER_PLACED: [
                (AgentName.STORE,         'assign_device_unique_id'),
                (AgentName.NOTIFICATION,  'send_order_confirmation'),
                (AgentName.AUDIT,         'log_order_placed'),
            ],
            AgentEvent.ORDER_SHIPPED: [
                (AgentName.NOTIFICATION,  'send_shipping_notification'),
                (AgentName.AUDIT,         'log_shipment'),
            ],

            # ─── Timezone ────────────────────────────────────────────
            AgentEvent.TIMEZONE_CHANGED: [
                (AgentName.REMINDER,      'regenerate_all_reminders_new_tz'),
                (AgentName.AUDIT,         'log_timezone_change'),
            ],

            # ─── Admin / System ──────────────────────────────────────
            AgentEvent.SYSTEM_ALERT: [
                (AgentName.NOTIFICATION,  'send_system_alert'),
                (AgentName.ADMIN,         'log_system_alert'),
            ],
        }

    def handover(
        self,
        from_agent: AgentName,
        to_agent: AgentName,
        event: AgentEvent,
        payload: HandoverPayload,
    ) -> HandoverResult:
        """Direct point-to-point handover between two agents"""
        logger.info(
            f'HANDOVER | {from_agent} → {to_agent} | event={event} | '
            f'trace={payload.trace_id}'
        )
        try:
            agent = self.registry.get(to_agent)
            method_name = self._resolve_method(to_agent, event)
            method = getattr(agent, method_name)
            result = method(payload)
            return HandoverResult(success=True, data=result or {}, agent=to_agent,
                                  trace_id=payload.trace_id)
        except AgentNotFoundError as e:
            logger.error(f'Agent not found: {to_agent} | {e}')
            return HandoverResult(success=False, error=str(e), agent=to_agent)
        except Exception as e:
            logger.exception(f'Handover failed | {from_agent}→{to_agent} | {e}')
            return HandoverResult(success=False, error=str(e), agent=to_agent)

    def broadcast(
        self,
        from_agent: AgentName,
        event: AgentEvent,
        payload: HandoverPayload,
    ) -> list[HandoverResult]:
        """
        Broadcast an event to all registered handlers.
        Used for events with multiple downstream consumers.
        Failures in one handler do NOT block others.
        """
        handlers = self._event_handlers.get(event, [])
        if not handlers:
            logger.warning(f'No handlers for event: {event}')
            return []

        results = []
        for agent_name, method_name in handlers:
            result = self._safe_call(agent_name, method_name, payload)
            results.append(result)
        return results

    def _safe_call(self, agent_name: AgentName, method_name: str,
                   payload: HandoverPayload) -> HandoverResult:
        try:
            agent = self.registry.get(agent_name)
            method = getattr(agent, method_name, None)
            if not method:
                raise AttributeError(f'{agent_name} has no method {method_name}')
            result = method(payload)
            return HandoverResult(success=True, data=result or {},
                                  agent=agent_name, trace_id=payload.trace_id)
        except Exception as e:
            logger.error(f'Handler failed: {agent_name}.{method_name} | {e}')
            return HandoverResult(success=False, error=str(e),
                                  agent=agent_name, trace_id=payload.trace_id)

    def _resolve_method(self, agent_name: AgentName, event: AgentEvent) -> str:
        handlers = self._event_handlers.get(event, [])
        for name, method in handlers:
            if name == agent_name:
                return method
        raise ValueError(f'{agent_name} has no handler for {event}')


# Global orchestrator singleton
orchestrator = AgentOrchestrator()

def get_orchestrator():
    return orchestrator


# ═══════════════════════════════════════════════════════════════════
# 4. BASE AGENT
# ═══════════════════════════════════════════════════════════════════

class BaseAgent:
    """
    All agents inherit from BaseAgent.
    Agents are stateless services — no instance variables across calls.
    All state lives in the database.
    """
    agent_name: AgentName = None

    def __init__(self):
        if self.agent_name:
            AgentRegistry.register(self.agent_name, self)

    def log(self, level: str, message: str, payload: HandoverPayload = None):
        extra = {'trace_id': payload.trace_id if payload else 'N/A'}
        getattr(logger, level)(f'[{self.agent_name}] {message}', extra=extra)


# ═══════════════════════════════════════════════════════════════════
# 5. AUTH AGENT
# ═══════════════════════════════════════════════════════════════════

class AuthAgent(BaseAgent):
    """
    Owns: user registration, login, JWT sessions, MFA, password management.
    
    Handover In:
        - None (Auth is the entry point for all authenticated flows)
    
    Handover Out:
        → PatientAgent      : USER_REGISTERED  → initialize_patient_profile
        → SubscriptionAgent : USER_REGISTERED  → assign_free_plan
        → AuditAgent        : Every auth event
    """
    agent_name = AgentName.AUTH

    def register_user(self, email: str, password: str, full_name: str,
                      role: str, phone: str = None) -> dict:
        from apps.identity.services import UserRegistrationService
        with transaction.atomic():
            user = UserRegistrationService.create(
                email=email, password=password,
                full_name=full_name, role=role, phone=phone
            )
            payload = HandoverPayload(user_id=str(user.id), data={'role': role})
            orchestrator.broadcast(AgentName.AUTH, AgentEvent.USER_REGISTERED, payload)
        return {'user_id': str(user.id), 'email': user.email}

    def login(self, email: str, password: str, device_info: dict) -> dict:
        from apps.identity.services import AuthService
        result = AuthService.authenticate(email, password, device_info)
        payload = HandoverPayload(
            user_id=str(result['user'].id),
            data={'device_type': device_info.get('device_type'), 'ip': device_info.get('ip')}
        )
        orchestrator.handover(AgentName.AUTH, AgentName.AUDIT,
                              AgentEvent.USER_LOGIN, payload)
        return result

    def revoke_all_sessions(self, payload: HandoverPayload) -> dict:
        """Called by orchestrator on password change"""
        from apps.identity.models import UserSession
        count = UserSession.objects.filter(
            user_id=payload.user_id,
            revoked_at__isnull=True
        ).update(
            revoked_at=timezone.now(),
            revoke_reason='password_changed'
        )
        self.log('info', f'Revoked {count} sessions', payload)
        return {'revoked_sessions': count}

    def verify_mfa(self, user_id: str, code: str) -> bool:
        from apps.identity.services import MFAService
        return MFAService.verify_totp_or_sms(user_id, code)


# ═══════════════════════════════════════════════════════════════════
# 6. PATIENT AGENT
# ═══════════════════════════════════════════════════════════════════

class PatientAgent(BaseAgent):
    """
    Owns: patient profile, medical conditions, onboarding flow.
    
    Handover In:
        ← AuthAgent      : USER_REGISTERED      → initialize_patient_profile
        ← MedicationAgent: PRESCRIPTION_CREATED  → (patient context)
    
    Handover Out:
        → ReminderAgent  : TIMEZONE_CHANGED     → regenerate_all_reminders_new_tz
        → AuditAgent     : profile updates
    """
    agent_name = AgentName.PATIENT

    def initialize_patient_profile(self, payload: HandoverPayload) -> dict:
        """Called by orchestrator after USER_REGISTERED"""
        from apps.clinical.models import Patient
        from apps.identity.models import User
        user = User.objects.get(id=payload.user_id)
        if user.role == 'PATIENT':
            import string, random
            code = 'PAT-' + ''.join(random.choices(string.digits, k=8))
            patient = Patient.objects.create(
                user=user,
                patient_code=code,
                timezone='Asia/Kolkata',
                primary_language='en',
            )
            self.log('info', f'Patient profile initialized: {patient.patient_code}', payload)
            return {'patient_id': str(patient.id)}
        return {}

    def handle_timezone_change(self, patient_id: str, new_timezone: str,
                                changed_by_user_id: str) -> dict:
        from apps.clinical.models import Patient
        patient = Patient.objects.get(id=patient_id)
        old_tz = patient.timezone
        patient.timezone = new_timezone
        patient.save(update_fields=['timezone', 'updated_at'])
        payload = HandoverPayload(
            patient_id=patient_id,
            data={'old_timezone': old_tz, 'new_timezone': new_timezone}
        )
        orchestrator.broadcast(AgentName.PATIENT, AgentEvent.TIMEZONE_CHANGED, payload)
        return {'status': 'timezone_updated', 'new_timezone': new_timezone}

    def mark_hospitalized(self, patient_id: str, expected_discharge: datetime = None) -> dict:
        from apps.clinical.models import Patient
        Patient.objects.filter(id=patient_id).update(
            is_hospitalized=True,
            hospitalized_since=timezone.now(),
            discharge_expected_at=expected_discharge,
        )
        payload = HandoverPayload(patient_id=patient_id)
        orchestrator.broadcast(AgentName.PATIENT, AgentEvent.PATIENT_HOSPITALIZED, payload)
        return {'status': 'patient_hospitalized'}


# ═══════════════════════════════════════════════════════════════════
# 7. CAREGIVER AGENT
# ═══════════════════════════════════════════════════════════════════

class CaregiverAgent(BaseAgent):
    """
    Owns: caregiver linking, permission management, caregiver alert dispatch.
    
    Handover In:
        ← AdherenceAgent : DOSE_LOGGED      → notify_caregivers_if_watched
        ← AIAgent        : HIGH_RISK_DETECTED → send_high_risk_alert_to_caregivers
    
    Handover Out:
        → NotificationAgent : alert dispatch
        → AuditAgent        : all caregiver actions
    """
    agent_name = AgentName.CAREGIVER

    def notify_caregivers_if_watched(self, payload: HandoverPayload) -> dict:
        """
        Called when a dose is logged (taken OR missed).
        Only notifies caregivers who have can_receive_alerts=True.
        Respects caregiver's own notification preferences.
        """
        from apps.clinical.models import PatientCaregiverLink
        status = payload.data.get('status')
        # Only alert on missed/late doses unless caregiver wants all updates
        if status == 'TAKEN' and not payload.data.get('notify_on_taken', False):
            return {'notified': 0}

        links = PatientCaregiverLink.objects.filter(
            patient_id=payload.patient_id,
            can_receive_alerts=True,
            is_active=True,
        ).select_related('caregiver__user')

        notified = 0
        for link in links:
            notif_payload = HandoverPayload(
                user_id=str(link.caregiver.user.id),
                patient_id=payload.patient_id,
                data={
                    'type':         'DOSE_STATUS_UPDATE',
                    'status':       status,
                    'medication':   payload.data.get('medication_name'),
                    'scheduled_at': payload.data.get('scheduled_at'),
                }
            )
            orchestrator.handover(AgentName.CAREGIVER, AgentName.NOTIFICATION,
                                  AgentEvent.REMINDER_SENT, notif_payload)
            notified += 1
        return {'notified': notified}

    def send_high_risk_alert_to_caregivers(self, payload: HandoverPayload) -> dict:
        """Broadcasts high-risk AI alert to all caregivers of the patient"""
        from apps.clinical.models import PatientCaregiverLink
        links = PatientCaregiverLink.objects.filter(
            patient_id=payload.patient_id,
            can_receive_alerts=True,
            is_active=True,
        ).select_related('caregiver__user')

        for link in links:
            notif_payload = HandoverPayload(
                user_id=str(link.caregiver.user.id),
                patient_id=payload.patient_id,
                data={
                    'type':        'HIGH_RISK_ALERT',
                    'risk_level':  payload.data.get('risk_level'),
                    'risk_score':  payload.data.get('risk_score'),
                    'reasons':     payload.data.get('reasons', []),
                }
            )
            orchestrator.handover(AgentName.CAREGIVER, AgentName.NOTIFICATION,
                                  AgentEvent.HIGH_RISK_DETECTED, notif_payload)
        return {'alerts_sent': links.count()}


# ═══════════════════════════════════════════════════════════════════
# 8. MEDICATION AGENT
# ═══════════════════════════════════════════════════════════════════

class MedicationAgent(BaseAgent):
    """
    Owns: medication catalog, prescriptions, schedules, drug interaction checks.
    
    Handover Out:
        → ReminderAgent : PRESCRIPTION_CREATED  → generate_reminder_schedule
        → AIAgent       : PRESCRIPTION_CREATED  → update_schedule_complexity_score
        → AuditAgent    : all prescription changes
    """
    agent_name = AgentName.MEDICATION

    def create_prescription(self, patient_id: str, data: dict,
                             created_by_user_id: str) -> dict:
        from apps.clinical.models import Prescription, Patient
        from apps.subscriptions.gates import check_medication_limit
        
        patient = Patient.objects.get(id=patient_id)
        check_medication_limit(patient.user)   # raises SubscriptionLimitError if over limit
        
        with transaction.atomic():
            prescription = Prescription.objects.create(
                patient=patient,
                **data
            )
            payload = HandoverPayload(
                patient_id=patient_id,
                prescription_id=str(prescription.id),
                data={'medication_id': str(prescription.medication_id)}
            )
            orchestrator.broadcast(AgentName.MEDICATION,
                                   AgentEvent.PRESCRIPTION_CREATED, payload)
        return {'prescription_id': str(prescription.id)}

    def validate_drug_interactions(self, payload: HandoverPayload) -> dict:
        """
        Called when new prescription created.
        Checks for known interactions with patient's existing medications.
        Currently: rule-based lookup. Future: ML-based interaction model.
        """
        from apps.clinical.services import DrugInteractionChecker
        interactions = DrugInteractionChecker.check(
            patient_id=payload.patient_id,
            new_prescription_id=payload.prescription_id
        )
        if interactions:
            warning_payload = HandoverPayload(
                patient_id=payload.patient_id,
                data={'interactions': interactions, 'severity': 'WARNING'}
            )
            orchestrator.handover(AgentName.MEDICATION, AgentName.NOTIFICATION,
                                  AgentEvent.SYSTEM_ALERT, warning_payload)
        return {'interactions_found': len(interactions)}


# ═══════════════════════════════════════════════════════════════════
# 9. REMINDER AGENT
# ═══════════════════════════════════════════════════════════════════

class ReminderAgent(BaseAgent):
    """
    Owns: reminder job generation, scheduling, escalation ladder.
    
    Handover In:
        ← MedicationAgent : PRESCRIPTION_CREATED  → generate_reminder_schedule
        ← MedicationAgent : SCHEDULE_UPDATED      → regenerate_future_reminders
        ← AdherenceAgent  : DOSE_LOGGED           → cancel_pending_escalation
        ← AdherenceAgent  : DOSE_MISSED           → start_escalation_ladder
    
    Handover Out:
        → NotificationAgent : reminder dispatch
        → CaregiverAgent    : escalation alerts
    """
    agent_name = AgentName.REMINDER

    ESCALATION_STEPS = [
        {'delay_minutes': 15,  'target': 'patient',    'channel': 'push'},
        {'delay_minutes': 30,  'target': 'patient',    'channel': 'sms'},
        {'delay_minutes': 60,  'target': 'caregiver',  'channel': 'push'},
        {'delay_minutes': 240, 'target': 'nurse',      'channel': 'call'},
        {'delay_minutes': 1440,'target': 'emergency',  'channel': 'sms'},
    ]

    def generate_reminder_schedule(self, payload: HandoverPayload) -> dict:
        """
        Called when prescription/schedule created.
        Generates all future reminder jobs for next 30 days.
        """
        from apps.scheduling.services import ScheduleGenerationService
        from apps.clinical.models import MedicationSchedule
        schedules = MedicationSchedule.objects.filter(
            prescription_id=payload.prescription_id,
            is_active=True
        )
        total_jobs = 0
        for schedule in schedules:
            jobs = ScheduleGenerationService().generate_upcoming_reminders(schedule, days=30)
            total_jobs += len(jobs)
        self.log('info', f'Generated {total_jobs} reminder jobs', payload)
        return {'reminder_jobs_created': total_jobs}

    def start_escalation_ladder(self, payload: HandoverPayload) -> dict:
        """
        Called when dose_missed detected.
        Schedules Celery tasks for each escalation step.
        """
        reminder_id = payload.reminder_id
        for step in self.ESCALATION_STEPS:
            eta = timezone.now() + timedelta(minutes=step['delay_minutes'])
            run_escalation_step.apply_async(
                kwargs={
                    'reminder_id': reminder_id,
                    'step':        step,
                    'patient_id':  payload.patient_id,
                },
                eta=eta,
                task_id=f'escalation-{reminder_id}-{step["delay_minutes"]}m'
            )
        return {'escalation_steps_scheduled': len(self.ESCALATION_STEPS)}

    def cancel_pending_escalation(self, payload: HandoverPayload) -> dict:
        """
        Called when dose is logged (patient took medication).
        Cancels all pending escalation tasks for this reminder.
        """
        from celery.app import app as celery_app
        from apps.scheduling.models import ReminderJob
        reminder_id = payload.reminder_id or payload.data.get('reminder_id')
        if not reminder_id:
            return {'cancelled': 0}
        # Cancel scheduled Celery tasks by task_id pattern
        for step in self.ESCALATION_STEPS:
            task_id = f'escalation-{reminder_id}-{step["delay_minutes"]}m'
            celery_app.control.revoke(task_id, terminate=False)
        ReminderJob.objects.filter(id=reminder_id).update(
            escalation_status='RESOLVED',
            escalation_resolved_at=timezone.now()
        )
        return {'cancelled': len(self.ESCALATION_STEPS)}

    def regenerate_all_reminders_new_tz(self, payload: HandoverPayload) -> dict:
        """Called on timezone change — cancel all future jobs and regenerate"""
        from apps.scheduling.models import ReminderJob
        cancelled = ReminderJob.objects.filter(
            schedule__prescription__patient_id=payload.patient_id,
            scheduled_at__gt=timezone.now(),
            status='PENDING'
        ).update(status='CANCELLED')
        # Re-generate with new timezone
        from apps.clinical.models import MedicationSchedule
        active_schedules = MedicationSchedule.objects.filter(
            prescription__patient_id=payload.patient_id,
            is_active=True
        )
        from apps.scheduling.services import ScheduleGenerationService
        svc = ScheduleGenerationService()
        new_jobs = sum(
            len(svc.generate_upcoming_reminders(s))
            for s in active_schedules
        )
        return {'cancelled_jobs': cancelled, 'new_jobs': new_jobs}


# ═══════════════════════════════════════════════════════════════════
# 10. ADHERENCE AGENT
# ═══════════════════════════════════════════════════════════════════

class AdherenceAgent(BaseAgent):
    """
    Owns: dose event logging, adherence rate calculation, streak tracking.
    THE most critical agent in the system.
    
    Handover In:
        ← IoTAgent : DEVICE_EVENT_RECEIVED → log_dose_from_iot
    
    Handover Out:
        → ReminderAgent  : DOSE_LOGGED   → cancel_pending_escalation
        → ReminderAgent  : DOSE_MISSED   → start_escalation_ladder
        → AIAgent        : DOSE_LOGGED   → trigger_realtime_risk_update
        → CaregiverAgent : DOSE_LOGGED   → notify_caregivers_if_watched
        → AuditAgent     : every dose event
    """
    agent_name = AgentName.ADHERENCE

    def log_dose(self, patient_id: str, prescription_id: str,
                 scheduled_at: datetime, taken_at: datetime = None,
                 source: str = 'APP_MANUAL', device_id: str = None,
                 actor_id: str = None) -> dict:
        from apps.telemetry.models import AdherenceEvent, AdherenceStatus
        from apps.clinical.models import Prescription

        prescription = Prescription.objects.get(id=prescription_id)
        late_minutes = None
        if taken_at:
            late_minutes = int((taken_at - scheduled_at).total_seconds() / 60)
            if late_minutes < -15:
                status = 'TAKEN_EARLY'
            elif late_minutes > 15:
                status = 'TAKEN_LATE'
            else:
                status = 'TAKEN'
        else:
            status = 'MISSED'

        event, created = AdherenceEvent.objects.get_or_create(
            prescription=prescription,
            scheduled_at=scheduled_at,
            defaults={
                'patient_id':    patient_id,
                'taken_at':      taken_at or timezone.now(),
                'status':        status,
                'log_method':    source,
                'device_id':     device_id,
                'late_minutes':  late_minutes,
            }
        )

        if created:
            payload = HandoverPayload(
                patient_id=patient_id,
                prescription_id=prescription_id,
                reminder_id=str(event.reminder_job_id) if event.reminder_job_id else None,
                data={
                    'status':          status,
                    'medication_name': prescription.medication.name,
                    'scheduled_at':    scheduled_at.isoformat(),
                    'late_minutes':    late_minutes,
                    'source':          source,
                }
            )
            event_type = AgentEvent.DOSE_LOGGED if status != 'MISSED' else AgentEvent.DOSE_MISSED
            orchestrator.broadcast(AgentName.ADHERENCE, event_type, payload)

        return {'event_id': str(event.id), 'status': status, 'created': created}

    def log_dose_from_iot(self, payload: HandoverPayload) -> dict:
        """Called by IoTAgent when device event translates to a dose action"""
        device_payload = payload.data
        return self.log_dose(
            patient_id=payload.patient_id,
            prescription_id=device_payload['prescription_id'],
            scheduled_at=datetime.fromisoformat(device_payload['scheduled_at']),
            taken_at=datetime.fromisoformat(device_payload['taken_at']),
            source='IOT_PILLBOX',
            device_id=payload.device_id,
        )

    def get_adherence_rate(self, patient_id: str, days: int = 30,
                            medication_id: str = None) -> dict:
        from apps.telemetry.models import AdherenceEvent
        from django.db.models import Count, Q
        qs = AdherenceEvent.objects.filter(
            patient_id=patient_id,
            scheduled_at__gte=timezone.now() - timedelta(days=days),
            deleted_at__isnull=True
        )
        if medication_id:
            qs = qs.filter(prescription__medication_id=medication_id)
        totals = qs.aggregate(
            total=Count('id'),
            taken=Count('id', filter=Q(status__in=['TAKEN', 'TAKEN_LATE', 'TAKEN_EARLY'])),
            missed=Count('id', filter=Q(status='MISSED')),
        )
        rate = round(totals['taken'] / totals['total'] * 100, 2) if totals['total'] else None
        return {**totals, 'adherence_rate': rate, 'period_days': days}


# ═══════════════════════════════════════════════════════════════════
# 11. NOTIFICATION AGENT
# ═══════════════════════════════════════════════════════════════════

class NotificationAgent(BaseAgent):
    """
    Owns: multi-channel notification dispatch (push, SMS, WhatsApp, email, voice).
    Never delivers directly — delegates to channel-specific Celery tasks.
    
    Handover In: receives from almost every other agent
    Handover Out: → AuditAgent (every notification logged)
    """
    agent_name = AgentName.NOTIFICATION

    CHANNEL_TASK_MAP = {
        'push':     'notifications.tasks.send_push',
        'sms':      'notifications.tasks.send_sms',
        'whatsapp': 'notifications.tasks.send_whatsapp',
        'email':    'notifications.tasks.send_email',
        'voice':    'notifications.tasks.send_voice_call',
    }

    # Channels available per subscription plan
    PLAN_CHANNELS = {
        'free':      ['push'],
        'freemium':  ['push', 'sms', 'email'],
        'premium':   ['push', 'sms', 'email', 'whatsapp', 'voice'],
    }

    def dispatch(self, payload: HandoverPayload) -> dict:
        from apps.identity.models import User, NotificationPreferences
        user = User.objects.get(id=payload.user_id)
        prefs = user.notification_preferences
        plan = user.subscription.plan.slug

        channels = self._resolve_channels(user, prefs, plan, payload.data)
        sent_to = []
        for channel in channels:
            task_path = self.CHANNEL_TASK_MAP[channel]
            from celery import current_app
            current_app.send_task(task_path, kwargs={
                'user_id': str(user.id),
                'payload': payload.data,
            })
            sent_to.append(channel)
        return {'channels': sent_to}

    # Notification Agent also responds to broadcast events
    def send_welcome_notification(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'WELCOME'
        return self.dispatch(payload)

    def send_whatsapp_welcome(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'WHATSAPP_WELCOME'
        return self.dispatch(payload)

    def send_order_confirmation(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'ORDER_CONFIRMATION'
        return self.dispatch(payload)

    def send_device_linked_confirmation(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'DEVICE_LINKED'
        return self.dispatch(payload)

    def send_low_battery_alert(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'DEVICE_LOW_BATTERY'
        return self.dispatch(payload)

    def send_security_alert(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'SECURITY_ALERT'
        # Force email for security alerts regardless of preferences
        payload.data['force_channel'] = 'email'
        return self.dispatch(payload)

    def send_patient_risk_notification(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'HIGH_RISK_ALERT'
        
        try:
            from apps.identity.models import User
            user = User.objects.get(id=payload.user_id)
            lang = user.preferred_language
            if lang != 'en' and payload.data.get('reasons'):
                from apps.ai_engine.services.translation import TranslationService
                payload.data['reasons'] = TranslationService.batch_translate(payload.data['reasons'], lang)
        except Exception as e:
            self.log('warning', f'Failed to translate notification: {e}', payload)
            
        return self.dispatch(payload)

    def send_insight_notification(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'AI_INSIGHT'
        
        try:
            from apps.identity.models import User
            user = User.objects.get(id=payload.user_id)
            lang = user.preferred_language
            if lang != 'en' and payload.data.get('pattern'):
                from apps.ai_engine.services.translation import TranslationService
                # The pattern could be a string or object. Assuming string based on InsightEngine.
                payload.data['pattern'] = TranslationService.translate_text(payload.data['pattern'], lang)
        except Exception as e:
            self.log('warning', f'Failed to translate insight: {e}', payload)
            
        return self.dispatch(payload)

    def send_system_alert(self, payload: HandoverPayload) -> dict:
        payload.data['type'] = 'SYSTEM_ALERT'
        # Force email or critical push
        payload.data['force_channel'] = 'email'
        return self.dispatch(payload)

    def _resolve_channels(self, user, prefs, plan: str, data: dict) -> list[str]:
        if data.get('force_channel'):
            return [data['force_channel']]
        allowed = set(self.PLAN_CHANNELS.get(plan, ['push']))
        preferred = []
        if prefs.push_enabled and 'push' in allowed:
            preferred.append('push')
        if prefs.sms_enabled and 'sms' in allowed:
            preferred.append('sms')
        if prefs.email_enabled and 'email' in allowed:
            preferred.append('email')
        if prefs.whatsapp_enabled and 'whatsapp' in allowed:
            preferred.append('whatsapp')
        if prefs.voice_call_enabled and 'voice' in allowed:
            preferred.append('voice')
        return preferred or ['push']


# ═══════════════════════════════════════════════════════════════════
# 12. IoT AGENT
# ═══════════════════════════════════════════════════════════════════

class IoTAgent(BaseAgent):
    """
    Owns: device unique ID generation, device linking, IoT event ingestion,
          device heartbeat processing, device-to-adherence translation.
    
    Handover Out:
        → AdherenceAgent    : DEVICE_EVENT_RECEIVED → log_dose_from_iot
        → NotificationAgent : low battery, device offline
        → AuditAgent        : device link/unlink, events
    """
    agent_name = AgentName.IOT

    def link_device(self, user_id: str, unique_code: str,
                    device_name: str = 'Smart Pillbox') -> dict:
        """
        Full device linking flow.
        1. Validate unique code
        2. Check PREMIUM subscription
        3. Create Device record
        4. Mark DeviceUniqueID as provisioned
        5. Return device credentials for firmware setup
        """
        from apps.store.models import DeviceUniqueID
        from apps.iot.models import Device
        from apps.subscriptions.gates import require_feature

        require_feature(user_id, 'hardware_linking')  # raises if not PREMIUM

        uid = DeviceUniqueID.objects.select_for_update().get(unique_code=unique_code)
        if uid.is_provisioned:
            raise ValueError('Device already linked to another account')

        with transaction.atomic():
            device = Device.objects.create(
                user_id=user_id,
                unique_id_record=uid,
                device_name=device_name,
                api_key=secrets.token_urlsafe(32),
                is_active=True,
            )
            uid.is_provisioned = True
            uid.provisioned_at = timezone.now()
            uid.save()

        payload = HandoverPayload(
            user_id=user_id,
            device_id=str(device.id),
            data={'unique_code': unique_code, 'device_name': device_name}
        )
        orchestrator.broadcast(AgentName.IOT, AgentEvent.DEVICE_LINKED, payload)
        return {'device_id': str(device.id), 'api_key': device.api_key}

    def ingest_event(self, device: Any, raw_payload: dict) -> dict:
        """
        Entry point for all IoT device events.
        Translates hardware event → domain event → hands off to AdherenceAgent.
        """
        from apps.iot.models import DeviceEvent
        event_uuid = raw_payload.get('event_uuid', str(uuid.uuid4()))
        event, created = DeviceEvent.objects.get_or_create(
            event_uuid=event_uuid,
            defaults={'device': device, 'raw_payload': raw_payload,
                      'event_type': raw_payload.get('event_type')}
        )
        if not created:
            return {'status': 'duplicate_ignored', 'event_id': str(event.id)}

        translated = self._translate_event(device, event, raw_payload)
        if translated:
            payload = HandoverPayload(
                patient_id=str(device.linked_patient_id) if device.linked_patient_id else None,
                device_id=str(device.id),
                data=translated
            )
            orchestrator.broadcast(AgentName.IOT, AgentEvent.DEVICE_EVENT_RECEIVED, payload)
        return {'status': 'accepted', 'event_id': str(event.id)}

    def process_heartbeat(self, device: Any, heartbeat: dict) -> dict:
        """Update device status from heartbeat"""
        from apps.iot.models import Device, DeviceHeartbeat
        battery = heartbeat.get('battery_level', 0)
        Device.objects.filter(id=device.id).update(
            last_seen_at=timezone.now(),
            battery_level=battery,
            firmware_version=heartbeat.get('firmware_version', device.firmware_version),
        )
        DeviceHeartbeat.objects.create(device=device, **heartbeat)
        if battery < 15:
            payload = HandoverPayload(
                user_id=str(device.user_id),
                device_id=str(device.id),
                data={'battery_level': battery, 'device_name': device.device_name}
            )
            orchestrator.broadcast(AgentName.IOT, AgentEvent.DEVICE_LOW_BATTERY, payload)
        return {'battery_level': battery}

    def _translate_event(self, device, event, raw_payload: dict) -> Optional[dict]:
        """Maps hardware event types to adherence context"""
        event_type = raw_payload.get('event_type')
        compartment = raw_payload.get('compartment')
        EVENT_TRANSLATION = {
            'COMPARTMENT_OPENED': 'DOSE_TAKEN',
            'DOSE_DISPENSED':     'DOSE_TAKEN',
            'DOOR_OPENED':        'DOSE_TAKEN',
        }
        if event_type not in EVENT_TRANSLATION:
            return None   # Non-adherence events (door_closed, etc.) not translated
        # Resolve which prescription is in this compartment
        from apps.iot.models import DeviceCompartmentMapping
        mapping = DeviceCompartmentMapping.objects.filter(
            device=device, compartment_number=compartment
        ).first()
        if not mapping:
            return None
        return {
            'prescription_id': str(mapping.prescription_id),
            'scheduled_at':    mapping.next_scheduled_time.isoformat(),
            'taken_at':        raw_payload.get('timestamp', timezone.now().isoformat()),
        }

    def disable_device_sync(self, payload: HandoverPayload) -> dict:
        """Called when subscription expires — disable IoT sync for user"""
        from apps.iot.models import Device
        count = Device.objects.filter(
            user_id=payload.user_id,
            is_active=True
        ).update(is_active=False)
        return {'devices_disabled': count}


# ═══════════════════════════════════════════════════════════════════
# 13. AI AGENT
# ═══════════════════════════════════════════════════════════════════

class AIAgent(BaseAgent):
    """
    Owns: risk scoring, AI insights, pattern detection, recommendations.
    Advisory only — NEVER auto-changes clinical data.
    
    Handover In:
        ← AdherenceAgent  : DOSE_LOGGED      → trigger_realtime_risk_update
        ← MedicationAgent : PRESCRIPTION_CREATED → update_schedule_complexity_score
    
    Handover Out:
        → CaregiverAgent    : HIGH_RISK_DETECTED → send alerts
        → NotificationAgent : patient risk notifications
        → AuditAgent        : risk score changes
    """
    agent_name = AgentName.AI

    def trigger_realtime_risk_update(self, payload: HandoverPayload) -> dict:
        """Called after every dose event (PREMIUM only)"""
        from apps.subscriptions.gates import check_feature
        from apps.identity.models import User
        patient_user = User.objects.get(patient__id=payload.patient_id)
        if not check_feature(patient_user, 'ai_insights_realtime'):
            return {'skipped': 'not_premium'}
        from apps.ai_engine.tasks import compute_risk_score
        compute_risk_score.delay(payload.patient_id, trigger='DOSE_EVENT',
                                 trace_id=payload.trace_id)
        return {'queued': True}

    def compute_and_store_risk(self, patient_id: str, trigger: str) -> dict:
        """Core risk computation — called by Celery task"""
        from apps.ai_engine.services.risk_engine import RiskEngine
        result = RiskEngine.get_risk_score(patient_id, force_refresh=True)
        # Note: RiskEngine already stores the score and the Celery task broadcasts high risk
        return {'risk_score': float(result.get('risk_score', 0)), 'risk_level': result.get('risk_level', 'medium')}

    def flag_missed_dose_pattern(self, payload: HandoverPayload) -> dict:
        """Detects recurring miss patterns (e.g., always misses evening Mon/Wed)"""
        from apps.ai_engine.services.insight_engine import InsightEngine
        patterns = InsightEngine.generate(payload.patient_id)
        if patterns:
            for pattern in patterns:
                # Generate insight for detected pattern
                insight_payload = HandoverPayload(
                    patient_id=payload.patient_id,
                    data={'pattern': pattern}
                )
                orchestrator.broadcast(AgentName.AI, AgentEvent.INSIGHT_GENERATED,
                                       insight_payload)
        return {'patterns_found': len(patterns)}

    def update_schedule_complexity_score(self, payload: HandoverPayload) -> dict:
        """Recomputes schedule complexity after new prescription"""
        from apps.clinical.models import Prescription
        score = Prescription.objects.filter(patient_id=payload.patient_id, status='active').count()
        return {'complexity_score': score}


# ═══════════════════════════════════════════════════════════════════
# 14. SUBSCRIPTION AGENT
# ═══════════════════════════════════════════════════════════════════

class SubscriptionAgent(BaseAgent):
    """
    Owns: plan management, feature gating, billing events, upgrade/downgrade.
    
    Handover In:
        ← AuthAgent : USER_REGISTERED → assign_free_plan
    
    Handover Out:
        → ReminderAgent     : SUBSCRIPTION_UPGRADED   → unlock_premium_channels
        → ReminderAgent     : SUBSCRIPTION_EXPIRED    → downgrade channels
        → IoTAgent          : SUBSCRIPTION_EXPIRED    → disable device sync
        → NotificationAgent : all subscription events
    """
    agent_name = AgentName.SUBSCRIPTION

    def assign_free_plan(self, payload: HandoverPayload) -> dict:
        """Called automatically on user registration"""
        from apps.subscriptions.models import UserSubscription, SubscriptionPlan
        free_plan = SubscriptionPlan.objects.get(slug='free')
        sub = UserSubscription.objects.create(
            user_id=payload.user_id,
            plan=free_plan,
            status='ACTIVE',
            started_at=timezone.now(),
        )
        self.log('info', f'Free plan assigned to user {payload.user_id}', payload)
        return {'subscription_id': str(sub.id), 'plan': 'free'}

    def upgrade_plan(self, user_id: str, new_plan_slug: str,
                     payment_data: dict) -> dict:
        from apps.subscriptions.models import UserSubscription, SubscriptionPlan
        from apps.subscriptions.billing import BillingService

        new_plan = SubscriptionPlan.objects.get(slug=new_plan_slug)
        sub = UserSubscription.objects.get(user_id=user_id)
        old_plan_slug = sub.plan.slug

        invoice = BillingService.create_and_charge(user_id, new_plan, payment_data)
        sub.plan = new_plan
        sub.status = 'ACTIVE'
        sub.started_at = timezone.now()
        sub.expires_at = timezone.now() + timedelta(days=30)
        sub.save()

        payload = HandoverPayload(
            user_id=user_id,
            data={'old_plan': old_plan_slug, 'new_plan': new_plan_slug,
                  'invoice_id': str(invoice.id)}
        )
        orchestrator.broadcast(AgentName.SUBSCRIPTION,
                               AgentEvent.SUBSCRIPTION_UPGRADED, payload)
        return {'plan': new_plan_slug, 'invoice_id': str(invoice.id)}


# ═══════════════════════════════════════════════════════════════════
# 15. STORE AGENT
# ═══════════════════════════════════════════════════════════════════

class StoreAgent(BaseAgent):
    """
    Owns: hardware product catalog, purchase orders, device unique ID assignment.
    
    Handover In:
        ← Orchestrator : ORDER_PLACED → assign_device_unique_id
    
    Handover Out:
        → NotificationAgent : order confirmation, shipping updates
        → AuditAgent        : all store transactions
    """
    agent_name = AgentName.STORE

    def place_order(self, user_id: str, product_id: str, quantity: int,
                    shipping_address: dict, payment_data: dict) -> dict:
        from apps.store.models import HardwareOrder, HardwareProduct
        from apps.store.billing import process_payment

        product = HardwareProduct.objects.select_for_update().get(id=product_id)
        if product.stock_count < quantity:
            raise ValueError('Insufficient stock')

        total_price = product.price * quantity
        payment = process_payment(user_id, total_price, payment_data)

        with transaction.atomic():
            order = HardwareOrder.objects.create(
                user_id=user_id,
                product=product,
                quantity=quantity,
                total_price=total_price,
                status='PAID',
                shipping_address=shipping_address,
                payment_id=payment['gateway_id'],
            )
            product.stock_count -= quantity
            product.save(update_fields=['stock_count'])

        payload = HandoverPayload(
            user_id=user_id,
            order_id=str(order.id),
            data={'product_id': product_id, 'quantity': quantity}
        )
        orchestrator.broadcast(AgentName.STORE, AgentEvent.ORDER_PLACED, payload)
        return {'order_id': str(order.id), 'status': 'PAID'}

    def assign_device_unique_id(self, payload: HandoverPayload) -> dict:
        """
        Called when order placed — reserves UniqueIDs for ordered devices.
        Each physical device in the order gets one unique code.
        """
        from apps.store.models import DeviceUniqueID, HardwareOrder
        order = HardwareOrder.objects.get(id=payload.order_id)
        available_ids = DeviceUniqueID.objects.filter(
            hardware_product=order.product,
            order__isnull=True,
            is_provisioned=False,
        )[:order.quantity]

        if available_ids.count() < order.quantity:
            raise ValueError('Not enough unassigned device IDs for this order')

        uid_codes = []
        for uid in available_ids:
            uid.order = order
            uid.save(update_fields=['order', 'updated_at'])
            uid_codes.append(uid.unique_code)

        return {'assigned_device_ids': uid_codes}


# ═══════════════════════════════════════════════════════════════════
# 16. ADMIN AGENT
# ═══════════════════════════════════════════════════════════════════

class AdminAgent(BaseAgent):
    """
    Owns: platform-level admin operations, metrics, system health.
    Exposes admin REST API endpoints.
    
    All admin actions generate AuditLog entries via AuditAgent handover.
    """
    agent_name = AgentName.ADMIN

    def get_platform_metrics(self) -> dict:
        """Admin dashboard overview metrics"""
        from apps.identity.models import User
        from apps.telemetry.models import AdherenceEvent
        from apps.subscriptions.models import UserSubscription
        from django.db.models import Count
        today = timezone.now().date()
        return {
            'users': {
                'total':   User.objects.filter(deleted_at__isnull=True).count(),
                'active':  User.objects.filter(is_active=True).count(),
                'today':   User.objects.filter(created_at__date=today).count(),
            },
            'subscriptions': {
                'free':     UserSubscription.objects.filter(plan__slug='free', status='ACTIVE').count(),
                'freemium': UserSubscription.objects.filter(plan__slug='freemium', status='ACTIVE').count(),
                'premium':  UserSubscription.objects.filter(plan__slug='premium', status='ACTIVE').count(),
            },
            'adherence_today': {
                'taken':  AdherenceEvent.objects.filter(scheduled_at__date=today, status='TAKEN').count(),
                'missed': AdherenceEvent.objects.filter(scheduled_at__date=today, status='MISSED').count(),
            },
        }

    def log_high_risk_event(self, payload: HandoverPayload) -> dict:
        """High-risk patients surface to admin dashboard"""
        cache_key = f'high_risk_patients:{payload.patient_id}'
        cache.set(cache_key, payload.data, timeout=3600)
        return {'flagged': True}

    def log_system_alert(self, payload: HandoverPayload) -> dict:
        """System alerts surface to admin dashboard"""
        cache_key = f'system_alerts:{payload.data.get("anomaly_id", payload.trace_id)}'
        cache.set(cache_key, payload.data, timeout=86400)
        return {'logged': True}

    def flag_device_offline(self, payload: HandoverPayload) -> dict:
        """Flags offline device in admin monitoring"""
        cache_key = f'offline_devices:{payload.device_id}'
        cache.set(cache_key, {'offline_since': timezone.now().isoformat()}, timeout=86400)
        return {'flagged': True}

    def get_device_id_inventory(self) -> dict:
        """Admin view of device ID stock"""
        from apps.store.models import DeviceUniqueID
        return {
            'total':       DeviceUniqueID.objects.count(),
            'unassigned':  DeviceUniqueID.objects.filter(order__isnull=True).count(),
            'assigned':    DeviceUniqueID.objects.filter(order__isnull=False, is_provisioned=False).count(),
            'provisioned': DeviceUniqueID.objects.filter(is_provisioned=True).count(),
        }


# ═══════════════════════════════════════════════════════════════════
# 17. AUDIT AGENT
# ═══════════════════════════════════════════════════════════════════

class AuditAgent(BaseAgent):
    """
    Owns: HIPAA audit trail. Immutable. Append-only.
    Every other agent calls AuditAgent — it never calls others.
    
    AuditAgent CANNOT be bypassed. It receives handovers from ALL agents.
    """
    agent_name = AgentName.AUDIT

    def log(self, payload: HandoverPayload, action: str,
            resource_type: str = '', resource_id: str = '') -> dict:
        from apps.audit.models import AuditLog
        try:
            AuditLog.objects.create(
                actor_id=payload.user_id,
                action=action,
                resource_type=resource_type or payload.data.get('resource_type', ''),
                resource_id=resource_id or payload.patient_id or payload.device_id or '',
                before_state=payload.data.get('before_state'),
                after_state=payload.data.get('after_state'),
                trace_id=payload.trace_id,
            )
        except Exception as e:
            # CRITICAL: Audit log failures MUST be logged externally (CloudWatch/Sentry)
            # but must NOT bubble up and fail the main transaction
            logger.critical(f'AUDIT LOG FAILURE: {action} | {e}')
        return {'logged': True}

    # Named methods called by orchestrator broadcast
    def log_registration(self, payload):
        return self.log(payload, 'USER_REGISTERED', 'User', payload.user_id)
    def log_password_change(self, payload):
        return self.log(payload, 'PASSWORD_CHANGED', 'User', payload.user_id)
    def log_dose_event(self, payload):
        return self.log(payload, 'DOSE_LOGGED', 'AdherenceEvent', payload.patient_id)
    def log_missed_dose(self, payload):
        return self.log(payload, 'DOSE_MISSED', 'AdherenceEvent', payload.patient_id)
    def log_prescription_created(self, payload):
        return self.log(payload, 'PRESCRIPTION_CREATED', 'Prescription', payload.prescription_id)
    def log_schedule_change(self, payload):
        return self.log(payload, 'SCHEDULE_UPDATED', 'MedicationSchedule')
    def log_device_linked(self, payload):
        return self.log(payload, 'DEVICE_LINKED', 'Device', payload.device_id)
    def log_device_event(self, payload):
        return self.log(payload, 'IOT_EVENT_RECEIVED', 'DeviceEvent', payload.device_id)
    def log_subscription_change(self, payload):
        return self.log(payload, 'SUBSCRIPTION_CHANGED', 'Subscription', payload.subscription_id)
    def log_subscription_expiry(self, payload):
        return self.log(payload, 'SUBSCRIPTION_EXPIRED', 'Subscription', payload.subscription_id)
    def log_risk_alert(self, payload):
        return self.log(payload, 'HIGH_RISK_ALERT', 'RiskScore', payload.patient_id)
    def log_order_placed(self, payload):
        return self.log(payload, 'ORDER_PLACED', 'HardwareOrder', payload.order_id)
    def log_shipment(self, payload):
        return self.log(payload, 'ORDER_SHIPPED', 'HardwareOrder', payload.order_id)
    def log_timezone_change(self, payload):
        return self.log(payload, 'TIMEZONE_CHANGED', 'Patient', payload.patient_id)
    def log_schedule_deactivated(self, payload):
        return self.log(payload, 'SCHEDULE_DEACTIVATED', 'MedicationSchedule')


# ═══════════════════════════════════════════════════════════════════
# 18. BACKGROUND JOB HANDOVER (Celery Tasks)
# ═══════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reminder(self, reminder_job_id: str):
    """
    Handover: ReminderAgent → NotificationAgent
    Triggered by ScheduleGenerationService at reminder eta
    """
    try:
        from apps.telemetry.models import ReminderJob
        job = ReminderJob.objects.select_related(
            'schedule__prescription__patient__user'
        ).get(id=reminder_job_id, status='PENDING')

        if job.schedule.prescription.patient.is_hospitalized:
            job.status = 'SKIPPED'
            job.save()
            return

        payload = HandoverPayload(
            patient_id=str(job.schedule.prescription.patient_id),
            user_id=str(job.schedule.prescription.patient.user_id),
            reminder_id=reminder_job_id,
            data={
                'type':            'MEDICATION_REMINDER',
                'medication_name': job.schedule.prescription.medication.name,
                'scheduled_at':    job.scheduled_at.isoformat(),
                'dose_value':      float(job.dose_value),
            }
        )
        notification_agent = AgentRegistry.get(AgentName.NOTIFICATION)
        notification_agent.dispatch(payload)
        job.status = 'SENT'
        job.sent_at = timezone.now()
        job.save()
        # Schedule escalation check
        check_dose_taken.apply_async(
            kwargs={'reminder_job_id': reminder_job_id},
            countdown=15 * 60   # check after 15 minutes
        )
    except ReminderJob.DoesNotExist:
        pass  # Job cancelled or already processed
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True)
def check_dose_taken(self, reminder_job_id: str):
    """
    Escalation trigger — called 15 min after reminder sent
    Handover: Celery → ReminderAgent.start_escalation_ladder
    """
    from apps.telemetry.models import ReminderJob
    job = ReminderJob.objects.get(id=reminder_job_id)
    if job.status == 'SENT':
        # Still not confirmed — start escalation
        payload = HandoverPayload(
            reminder_id=reminder_job_id,
            patient_id=str(job.schedule.prescription.patient_id),
            data={'missed_minutes': 15}
        )
        orchestrator.broadcast(AgentName.ADHERENCE, AgentEvent.DOSE_MISSED, payload)


@shared_task(bind=True, max_retries=5)
def run_escalation_step(self, reminder_id: str, step: dict, patient_id: str):
    """Executes one step of the escalation ladder"""
    from apps.telemetry.models import ReminderJob
    job = ReminderJob.objects.get(id=reminder_id)
    if job.status == 'TAKEN':
        return   # Patient confirmed — stop escalation
    payload = HandoverPayload(
        patient_id=patient_id,
        reminder_id=reminder_id,
        data={**step, 'escalation': True}
    )
    if step['target'] == 'patient':
        orchestrator.handover(AgentName.REMINDER, AgentName.NOTIFICATION,
                              AgentEvent.ESCALATION_TRIGGERED, payload)
    elif step['target'] in ('caregiver', 'nurse'):
        orchestrator.handover(AgentName.REMINDER, AgentName.CAREGIVER,
                              AgentEvent.ESCALATION_TRIGGERED, payload)


@shared_task
def compute_risk_score(patient_id: str, trigger: str = 'SCHEDULED', trace_id: str = None):
    """AI risk score computation — called by Celery Beat nightly and by AdherenceAgent"""
    ai_agent = AgentRegistry.get(AgentName.AI)
    return ai_agent.compute_and_store_risk(patient_id, trigger)


@shared_task
def batch_risk_score_all_patients():
    """Nightly Celery Beat task — score all FREEMIUM/PREMIUM patients"""
    from apps.clinical.models import Patient
    patients = Patient.objects.filter(
        user__subscription__plan__slug__in=['freemium', 'premium'],
        user__subscription__status='ACTIVE',
        deleted_at__isnull=True,
    ).values_list('id', flat=True)
    for pid in patients:
        compute_risk_score.delay(str(pid), trigger='NIGHTLY_BATCH')
    return {'patients_queued': len(patients)}


@shared_task
def check_subscription_expiries():
    """Daily task — handle expiring/expired subscriptions"""
    from apps.subscriptions.models import UserSubscription
    expired = UserSubscription.objects.filter(
        status='ACTIVE',
        expires_at__lt=timezone.now(),
        auto_renew=False
    )
    for sub in expired:
        sub.status = 'EXPIRED'
        sub.save()
        payload = HandoverPayload(
            user_id=str(sub.user_id),
            subscription_id=str(sub.id)
        )
        orchestrator.broadcast(AgentName.SUBSCRIPTION,
                               AgentEvent.SUBSCRIPTION_EXPIRED, payload)


@shared_task
def check_device_heartbeats():
    """Every 5 minutes — detect offline devices"""
    from apps.iot.models import Device
    threshold = timezone.now() - timedelta(minutes=15)
    offline_devices = Device.objects.filter(
        is_active=True,
        last_seen_at__lt=threshold
    )
    for device in offline_devices:
        payload = HandoverPayload(
            user_id=str(device.user_id),
            device_id=str(device.id),
            data={'last_seen': device.last_seen_at.isoformat()}
        )
        orchestrator.broadcast(AgentName.IOT, AgentEvent.DEVICE_OFFLINE, payload)


# ═══════════════════════════════════════════════════════════════════
# 19. ERROR BOUNDARIES
# ═══════════════════════════════════════════════════════════════════

class AgentNotFoundError(Exception):
    pass


class SubscriptionLimitError(Exception):
    def __init__(self, feature: str, current_plan: str = None, upgrade_url: str = None):
        self.feature     = feature
        self.current_plan= current_plan
        self.upgrade_url = upgrade_url
        super().__init__(f'Feature {feature} not available on {current_plan} plan')


class DeviceAlreadyLinkedError(Exception):
    pass


class InsufficientStockError(Exception):
    pass


# ═══════════════════════════════════════════════════════════════════
# 20. SYSTEM BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════

def bootstrap_agents():
    """
    Call this in Django AppConfig.ready() to instantiate all agents.
    Each agent self-registers in AgentRegistry on __init__.
    
    # apps/core/apps.py
    class CoreConfig(AppConfig):
        def ready(self):
            from agenthandover import bootstrap_agents
            bootstrap_agents()
    """
    agents = [
        AuthAgent(),
        PatientAgent(),
        CaregiverAgent(),
        MedicationAgent(),
        ReminderAgent(),
        AdherenceAgent(),
        NotificationAgent(),
        IoTAgent(),
        AIAgent(),
        SubscriptionAgent(),
        StoreAgent(),
        AdminAgent(),
        AuditAgent(),
    ]
    registered = [a.agent_name for a in agents]
    logger.info(f'MedAdhere agents bootstrapped: {registered}')
    return registered


# ─── Celery Beat Schedule ────────────────────────────────────────────────────

MEDADHERE_CELERY_BEAT_SCHEDULE = {
    'nightly-risk-scoring': {
        'task':     'agenthandover.batch_risk_score_all_patients',
        'schedule': '0 2 * * *',            # 2:00 AM UTC daily
    },
    'subscription-expiry-check': {
        'task':     'agenthandover.check_subscription_expiries',
        'schedule': '0 1 * * *',            # 1:00 AM UTC daily
    },
    'device-heartbeat-monitor': {
        'task':     'agenthandover.check_device_heartbeats',
        'schedule': '*/5 * * * *',          # Every 5 minutes
    },
}

# ─── End of agenthandover.py ────────────────────────────────────────────────
"""
QUICK REFERENCE: WHICH AGENT OWNS WHAT?

    AuthAgent          : login, register, JWT, sessions, MFA, password
    PatientAgent       : patient profile, conditions, hospitalization, timezone
    CaregiverAgent     : caregiver links, permissions, caregiver alert routing
    MedicationAgent    : drug catalog, prescriptions, schedules, interactions
    ReminderAgent      : reminder job generation, escalation ladder
    AdherenceAgent     : dose logging (all sources), rate calc, streaks
    NotificationAgent  : push, SMS, WhatsApp, email, voice dispatch
    IoTAgent           : device linking, unique ID provisioning, event ingestion
    AIAgent            : risk scores, insights, patterns (advisory only)
    SubscriptionAgent  : plans, feature gating, upgrade/downgrade, billing
    StoreAgent         : hardware catalog, orders, device ID assignment
    AdminAgent         : platform metrics, admin operations
    AuditAgent         : HIPAA-compliant immutable audit trail

INTER-AGENT RULE:
    Agent A → orchestrator.handover(A, B, event, payload) → Agent B
    NEVER: AgentA().some_method() called directly from AgentB
    ALWAYS: Go through orchestrator
"""
