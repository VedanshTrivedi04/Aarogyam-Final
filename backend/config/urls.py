"""
config/urls.py — Master URL Router (all 12 phases).
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from shared.health import HealthCheckView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Health Check (Phase 12) ──────────────────────────────────
    path('api/v1/health/', HealthCheckView.as_view(), name='health-check'),

    # ── Phase 1: Identity / Auth ─────────────────────────────────
    path('api/v1/auth/',          include('apps.identity.urls.auth')),
    path('api/v1/users/',         include('apps.identity.urls.users')),

    # ── Phase 2: Subscriptions & Billing ─────────────────────────
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),

    # ── Phase 3: Clinical ─────────────────────────────────────────
    path('api/v1/patients/',      include('apps.clinical.urls.patients')),
    path('api/v1/caregivers/',    include('apps.clinical.urls.caregivers')),
    path('api/v1/links/',         include('apps.clinical.urls.caregiver_links')),
    path('api/v1/medications/',   include('apps.clinical.urls.medications')),

    # ── Phase 4: Scheduling ───────────────────────────────────────
    path('api/v1/reminders/',     include('apps.scheduling.urls.reminders')),
    path('api/v1/adherence/',     include('apps.scheduling.urls.adherence')),

    # ── Phase 5 + 6: Telemetry / Celery ──────────────────────────
    path('api/v1/iot-telemetry/', include('apps.telemetry.urls')),

    # ── Phase 7: Notifications ────────────────────────────────────
    path('api/v1/notifications/', include('apps.notifications.urls')),

    # ── Communications: Real-time Chat & Call ────────────────────
    path('api/v1/communications/', include('apps.communications.urls')),

    # ── Phase 9: IoT Devices ──────────────────────────────────────
    path('api/v1/iot/',           include('apps.iot.urls')),

    # ── Phase 10: Store ───────────────────────────────────────────
    path('api/v1/store/',         include('apps.store.urls')),

    # ── Phase 13: Pharmacy ────────────────────────────────────────
    path('api/v1/pharmacy/',      include('apps.pharmacy.urls')),

    # ── Phase 14: Doctor Portal ───────────────────────────────────
    path('api/v1/doctor/',        include('apps.doctor_portal.urls')),

    # ── Phase 17: Family ──────────────────────────────────────────
    path('api/v1/family/',        include('apps.family.urls')),

    # ── Phase 19: Vitals ──────────────────────────────────────────
    path('api/v1/vitals/',        include('apps.vitals.urls')),

    # ── Phase 20: Gamification ────────────────────────────────────
    path('api/v1/gamification/',  include('apps.gamification.urls')),

    # ── Telegram Bot ──────────────────────────────────────────────
    path('api/v1/telegram/',      include('apps.telegram_bot.urls')),

    # ── Phase 11: Admin Panel API ─────────────────────────────────
    path('api/v1/admin/',         include('apps.admin_panel.urls')),

    # ── Phase 8: Audit Logs (admin only) ─────────────────────────
    path('api/v1/admin/audit-logs/', include('apps.audit.urls')),

    # ── Analytics (caregiver dashboards) ─────────────────────────
    path('api/v1/analytics/',     include('apps.analytics.urls')),

    # ── Phase 27: ABHA ───────────────────────────────────────────
    path('api/v1/abha/',          include('apps.abha.urls')),

    # ── Phase 24: Insurance Reports ─────────────────────────────
    path('api/v1/reports/',       include('apps.insurance_reports.urls')),

    # ── Phase 26: Geofencing ─────────────────────────────────────
    path('api/v1/geofence/',      include('apps.geofence.urls')),

    # ── Phase 21: Pharmacovigilance ─────────────────────────────
    path('api/v1/pharmacovigilance/', include('apps.pharmacovigilance.urls')),

    # ── AI Engine ────────────────────────────────────────────────
    path('api/v1/ai/',            include('apps.ai_engine.api', namespace='ai_engine')),

    # ── Agent Runtime (Agentic AI activity feed) ──────────────────
    path('api/v1/agent-runtime/', include('apps.agent_runtime.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
