"""
apps/admin_panel/views_super.py — Super Admin cross-portal monitoring API.
Kept separate from views.py: every endpoint here is IsSuperAdmin only (never
ADMIN), so the existing tenant-Admin surface in views.py stays untouched.
"""
from django.utils import timezone
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from shared.response import APIResponse
from shared.permissions import IsSuperAdmin


def _get_user_model():
    from django.contrib.auth import get_user_model
    return get_user_model()


def _adherence_7d():
    from apps.scheduling.models import AdherenceSummary
    result = AdherenceSummary.objects.filter(
        period_start__gte=timezone.now() - timezone.timedelta(days=7)
    ).aggregate(avg_rate=Avg('adherence_pct'))
    return round(result.get('avg_rate') or 0, 2)


def _portal_stats():
    """Single source of truth for per-portal numbers — reused by overview + breakdown."""
    User = _get_user_model()
    from apps.scheduling.models import ReminderJob
    from apps.pharmacy.models import RefillOrder

    today = timezone.now().date()

    patient_count   = User.objects.filter(role='PATIENT').count()
    caregiver_count = User.objects.filter(role='CAREGIVER').count()
    doctor_count    = User.objects.filter(role='DOCTOR').count()
    pharmacist_count = User.objects.filter(role='PHARMACIST').count()

    missed_jobs = ReminderJob.objects.filter(status='MISSED')
    missed_today = missed_jobs.filter(scheduled_at__date=today).count()
    missed_total_open = missed_jobs.count()

    refills = RefillOrder.objects.aggregate(
        pending=Count('id', filter=Q(status='PENDING')),
        failed=Count('id', filter=Q(status='FAILED')),
        total=Count('id'),
    )

    adherence_pct = _adherence_7d()

    return [
        {
            'portal': 'PATIENT',
            'label': 'Patient Portal',
            'active_users': patient_count,
            'pending_tasks': missed_today,
            'alerts': missed_total_open,
            'adherence_pct': adherence_pct,
        },
        {
            'portal': 'CAREGIVER',
            'label': 'Caregiver Portal',
            'active_users': caregiver_count,
            'pending_tasks': missed_total_open,
            'alerts': missed_total_open,
            'adherence_pct': None,
        },
        {
            'portal': 'DOCTOR',
            'label': 'Doctor Portal',
            'active_users': doctor_count,
            'pending_tasks': missed_total_open,
            'alerts': missed_total_open,
            'adherence_pct': None,
        },
        {
            'portal': 'PHARMACY',
            'label': 'Pharmacy Portal',
            'active_users': pharmacist_count,
            'pending_tasks': refills['pending'] or 0,
            'alerts': refills['failed'] or 0,
            'adherence_pct': None,
        },
    ]


class SuperAdminOverviewView(APIView):
    """GET /api/v1/admin/super/overview/ — top-line numbers across every portal."""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        User = _get_user_model()
        portals = _portal_stats()

        total_active_users = sum(p['active_users'] for p in portals)
        total_alerts = sum(p['alerts'] for p in portals)
        new_users_today = User.objects.filter(created_at__date=timezone.now().date()).count()

        return APIResponse.success({
            'total_active_users': total_active_users,
            'total_open_alerts': total_alerts,
            'global_adherence_pct': _adherence_7d(),
            'new_users_today': new_users_today,
        })


class SuperAdminPortalBreakdownView(APIView):
    """GET /api/v1/admin/super/portals/ — per-portal stat cards for the Dashboard grid."""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        return APIResponse.success(_portal_stats())


class SuperAdminPortalDetailView(APIView):
    """
    GET /api/v1/admin/super/portals/<portal>/detail/
    Drill-down from a Dashboard portal card into the underlying records.
    <portal> is one of PATIENT, CAREGIVER, DOCTOR, PHARMACY.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, portal):
        portal = (portal or '').upper()

        if portal == 'PHARMACY':
            from apps.pharmacy.models import RefillOrder
            orders = RefillOrder.objects.select_related(
                'patient__user', 'prescription__medication'
            ).order_by('-created_at')[:100]
            rows = [
                {
                    'id': str(o.id),
                    'patient': o.patient.user.full_name,
                    'medication': o.prescription.medication.name,
                    'status': o.status,
                    'quantity_ordered': o.quantity_ordered,
                    'total_amount': str(o.total_amount),
                    'estimated_delivery': o.estimated_delivery,
                    'failure_reason': o.failure_reason,
                }
                for o in orders
            ]
            return APIResponse.success({'portal': portal, 'rows': rows})

        if portal in ('PATIENT', 'CAREGIVER', 'DOCTOR'):
            from apps.scheduling.models import ReminderJob
            jobs = ReminderJob.objects.filter(status='MISSED').select_related(
                'schedule__prescription__patient__user',
                'schedule__prescription__medication',
            ).order_by('-scheduled_at')[:100]
            rows = [
                {
                    'id': str(j.id),
                    'patient': j.schedule.prescription.patient.user.full_name,
                    'medication': j.schedule.prescription.medication.name,
                    'scheduled_at': j.scheduled_at,
                    'dose_value': str(j.dose_value),
                    'dose_unit': j.dose_unit,
                    'status': j.status,
                }
                for j in jobs
            ]
            return APIResponse.success({'portal': portal, 'rows': rows})

        return APIResponse.error('Unknown portal.', code='NOT_FOUND', status=404)


class SuperAdminUserListView(APIView):
    """
    GET /api/v1/admin/super/users/?role=PATIENT&search=jane
    Full cross-role user directory with optional role filter and name/email search.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        User = _get_user_model()
        qs = User.objects.all().order_by('-created_at')

        role = request.query_params.get('role')
        if role:
            qs = qs.filter(role=role.upper())

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search))

        qs = qs[:200]
        data = [
            {
                'id': str(u.id),
                'email': u.email,
                'full_name': u.full_name,
                'role': u.role,
                'is_active': u.is_active,
                'date_joined': u.created_at,
            }
            for u in qs
        ]
        return APIResponse.success(data)


class SuperAdminChangeUserRoleView(APIView):
    """PATCH /api/v1/admin/super/users/{id}/role/ — {"role": "DOCTOR"}"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, pk):
        from apps.identity.models import UserRole
        User = _get_user_model()
        from django.shortcuts import get_object_or_404

        new_role = (request.data.get('role') or '').upper()
        if new_role not in UserRole.values:
            return APIResponse.error(
                f'Invalid role. Must be one of: {", ".join(UserRole.values)}',
                code='INVALID_ROLE', status=400,
            )

        user = get_object_or_404(User, id=pk)
        user.role = new_role
        user.save(update_fields=['role'])
        return APIResponse.success(
            {'id': str(user.id), 'role': user.role},
            message=f'Role updated to {new_role}.',
        )


class SuperAdminSetUserStatusView(APIView):
    """PATCH /api/v1/admin/super/users/{id}/status/ — {"is_active": true|false}"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, pk):
        User = _get_user_model()
        from django.shortcuts import get_object_or_404

        if 'is_active' not in request.data:
            return APIResponse.error('is_active is required.', code='MISSING_FIELD', status=400)

        user = get_object_or_404(User, id=pk)
        user.is_active = bool(request.data.get('is_active'))
        user.save(update_fields=['is_active'])
        status_label = 'activated' if user.is_active else 'deactivated'
        return APIResponse.success(
            {'id': str(user.id), 'is_active': user.is_active},
            message=f'User {status_label}.',
        )


class SuperAdminAuditLogView(APIView):
    """
    GET /api/v1/admin/super/audit/?action=&resource_type=&actor_id=&page=1
    Read-only, paginated view over the immutable AuditLog trail.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    PAGE_SIZE = 50

    def get(self, request):
        from apps.audit.models import AuditLog

        qs = AuditLog.objects.select_related('actor').all()

        action = request.query_params.get('action')
        if action:
            qs = qs.filter(action__icontains=action)

        resource_type = request.query_params.get('resource_type')
        if resource_type:
            qs = qs.filter(resource_type__icontains=resource_type)

        actor_id = request.query_params.get('actor_id')
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except ValueError:
            page = 1

        total = qs.count()
        start = (page - 1) * self.PAGE_SIZE
        rows = qs[start:start + self.PAGE_SIZE]

        data = [
            {
                'id': str(log.id),
                'created_at': log.created_at,
                'actor_email': log.actor.email if log.actor else None,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'ip_address': log.ip_address,
                'trace_id': log.trace_id,
            }
            for log in rows
        ]

        return APIResponse.success({
            'results': data,
            'page': page,
            'page_size': self.PAGE_SIZE,
            'total': total,
            'has_next': start + self.PAGE_SIZE < total,
        })


class SuperAdminTenantListCreateView(APIView):
    """
    GET  /api/v1/admin/super/tenants/ — list all tenants (SUPER_ADMIN-exclusive; regular
         ADMIN has no equivalent — a tenant admin only ever sees their own tenant).
    POST /api/v1/admin/super/tenants/ — create a tenant, reusing apps.tenants.services.TenantService.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.tenants.models import Tenant
        tenants = Tenant.objects.all().order_by('-created_at')
        data = [
            {
                'id': str(t.id),
                'name': t.name,
                'subdomain': t.subdomain,
                'plan': t.plan,
                'max_patients': t.max_patients,
                'is_active': t.is_active,
                'admin_count': t.admins.count(),
                'created_at': t.created_at,
            }
            for t in tenants
        ]
        return APIResponse.success(data)

    def post(self, request):
        from apps.tenants.services import TenantService
        from apps.tenants.models import Tenant

        name = (request.data.get('name') or '').strip()
        subdomain = (request.data.get('subdomain') or '').strip().lower()
        plan = request.data.get('plan', 'CLINIC')

        if not name or not subdomain:
            return APIResponse.error('name and subdomain are required.', code='MISSING_FIELD', status=400)

        if Tenant.objects.filter(subdomain=subdomain).exists():
            return APIResponse.error('A tenant with this subdomain already exists.', code='DUPLICATE', status=400)

        owner_user = None
        owner_user_id = request.data.get('owner_user_id')
        if owner_user_id:
            User = _get_user_model()
            from django.shortcuts import get_object_or_404
            owner_user = get_object_or_404(User, id=owner_user_id)

        tenant = TenantService.create_tenant(name=name, subdomain=subdomain, plan=plan, owner_user=owner_user)
        return APIResponse.success(
            {'id': str(tenant.id), 'name': tenant.name, 'subdomain': tenant.subdomain},
            message='Tenant created.',
        )


class SuperAdminTenantAssignAdminView(APIView):
    """POST /api/v1/admin/super/tenants/{id}/admins/ — {"user_id": "...", "is_primary": false}"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, pk):
        from apps.tenants.models import Tenant, TenantAdmin
        from django.shortcuts import get_object_or_404

        tenant = get_object_or_404(Tenant, id=pk)
        user_id = request.data.get('user_id')
        if not user_id:
            return APIResponse.error('user_id is required.', code='MISSING_FIELD', status=400)

        User = _get_user_model()
        user = get_object_or_404(User, id=user_id)

        admin_link, created = TenantAdmin.objects.get_or_create(
            tenant=tenant, user=user,
            defaults={'is_primary': bool(request.data.get('is_primary', False))},
        )
        if not created:
            return APIResponse.error('User is already an admin of this tenant.', code='DUPLICATE', status=400)

        return APIResponse.success(
            {'tenant_id': str(tenant.id), 'user_id': str(user.id), 'is_primary': admin_link.is_primary},
            message=f'{user.email} added as admin of {tenant.name}.',
        )


class SuperAdminTenantSetStatusView(APIView):
    """PATCH /api/v1/admin/super/tenants/{id}/status/ — {"is_active": true|false}"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, pk):
        from apps.tenants.models import Tenant
        from django.shortcuts import get_object_or_404

        if 'is_active' not in request.data:
            return APIResponse.error('is_active is required.', code='MISSING_FIELD', status=400)

        tenant = get_object_or_404(Tenant, id=pk)
        tenant.is_active = bool(request.data.get('is_active'))
        tenant.save(update_fields=['is_active'])
        return APIResponse.success({'id': str(tenant.id), 'is_active': tenant.is_active})


class SuperAdminBillingOverviewView(APIView):
    """
    GET /api/v1/admin/super/billing/
    Revenue/churn snapshot over SubscriptionPlan/UserSubscription/SubscriptionInvoice.
    List/extend actions already exist as AdminSubscriptionListView/AdminExtendSubscriptionView
    in views.py — this endpoint adds the aggregate numbers those don't compute.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.subscriptions.models import SubscriptionPlan, UserSubscription, SubscriptionInvoice

        by_plan = list(
            UserSubscription.objects.values('plan__name', 'status')
            .annotate(count=Count('id'))
            .order_by('plan__name', 'status')
        )

        status_counts = UserSubscription.objects.aggregate(
            active=Count('id', filter=Q(status='ACTIVE')),
            past_due=Count('id', filter=Q(status='PAST_DUE')),
            canceled=Count('id', filter=Q(status='CANCELED')),
            unpaid=Count('id', filter=Q(status='UNPAID')),
        )
        total_subs = sum(status_counts.values())
        churn_rate = round((status_counts['canceled'] / total_subs) * 100, 2) if total_subs else 0

        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        revenue_30d = SubscriptionInvoice.objects.filter(
            status='PAID', paid_at__gte=thirty_days_ago,
        ).aggregate(invoice_count=Count('id'), total_amount=Sum('amount'))

        expiring_soon = UserSubscription.objects.filter(
            status='ACTIVE',
            expires_at__isnull=False,
            expires_at__lte=timezone.now() + timezone.timedelta(days=7),
        ).select_related('user', 'plan').order_by('expires_at')[:20]

        return APIResponse.success({
            'status_counts': status_counts,
            'total_subscriptions': total_subs,
            'churn_rate_pct': churn_rate,
            'by_plan': by_plan,
            'paid_invoices_30d': revenue_30d['invoice_count'] or 0,
            'revenue_30d': str(revenue_30d['total_amount'] or 0),
            'plans': list(SubscriptionPlan.objects.values('name', 'slug', 'price_monthly', 'price_yearly')),
            'expiring_soon': [
                {
                    'user_email': s.user.email,
                    'plan': s.plan.name,
                    'expires_at': s.expires_at,
                }
                for s in expiring_soon
            ],
        })


class SuperAdminCaregiverSubscriptionsView(APIView):
    """
    GET /api/v1/admin/super/billing/caregivers/
    Every caregiver plus their subscription (or None if they've never had one) —
    Super Admin's single place to see and manage caregiver plans, which the
    generic AdminSubscriptionListView in views.py doesn't break out by role.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        User = _get_user_model()
        from apps.subscriptions.models import SubscriptionPlan

        caregivers = User.objects.filter(role='CAREGIVER').select_related(
            'subscription', 'subscription__plan'
        ).order_by('-created_at')

        rows = []
        for cg in caregivers:
            sub = getattr(cg, 'subscription', None)
            rows.append({
                'user_id': str(cg.id),
                'email': cg.email,
                'full_name': cg.full_name,
                'subscription': {
                    'id': str(sub.id),
                    'plan_name': sub.plan.name,
                    'plan_slug': sub.plan.slug,
                    'status': sub.status,
                    'expires_at': sub.expires_at,
                    'auto_renew': sub.auto_renew,
                } if sub else None,
            })

        return APIResponse.success({
            'caregivers': rows,
            'plans': list(SubscriptionPlan.objects.values('name', 'slug', 'price_monthly', 'price_yearly')),
        })


class SuperAdminCaregiverSubscriptionAssignView(APIView):
    """
    POST /api/v1/admin/super/billing/caregivers/{user_id}/subscription/
    Body: {"plan_slug": "premium", "days": 30}
    Creates the caregiver's subscription if they don't have one yet, or switches
    their existing one to the given plan (get_or_create keeps this idempotent).
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, user_id):
        from django.shortcuts import get_object_or_404
        from apps.subscriptions.models import SubscriptionPlan, UserSubscription
        import datetime

        User = _get_user_model()
        caregiver = get_object_or_404(User, id=user_id, role='CAREGIVER')

        plan_slug = request.data.get('plan_slug')
        if not plan_slug:
            return APIResponse.error('plan_slug is required.', code='MISSING_FIELD', status=400)
        plan = get_object_or_404(SubscriptionPlan, slug=plan_slug)

        days = request.data.get('days')
        expires_at = timezone.now() + datetime.timedelta(days=int(days)) if days else None

        sub, created = UserSubscription.objects.update_or_create(
            user=caregiver,
            defaults={'plan': plan, 'status': 'ACTIVE', 'expires_at': expires_at},
        )

        return APIResponse.success(
            {'id': str(sub.id), 'plan': plan.name, 'status': sub.status, 'expires_at': sub.expires_at},
            message=f'{"Assigned" if created else "Updated"} {plan.name} plan for {caregiver.email}.',
        )


class SuperAdminCaregiverSubscriptionActionView(APIView):
    """
    PATCH /api/v1/admin/super/billing/caregivers/{user_id}/subscription/extend/ — {"days": 30}
    PATCH /api/v1/admin/super/billing/caregivers/{user_id}/subscription/cancel/
    Two lightweight actions on an existing caregiver subscription. Extend reuses
    the same base+days logic as the generic AdminExtendSubscriptionView.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id, action):
        from django.shortcuts import get_object_or_404
        from apps.subscriptions.models import UserSubscription
        import datetime

        User = _get_user_model()
        caregiver = get_object_or_404(User, id=user_id, role='CAREGIVER')
        sub = get_object_or_404(UserSubscription, user=caregiver)

        if action == 'extend':
            days = int(request.data.get('days', 30))
            base = sub.expires_at or timezone.now()
            sub.expires_at = base + datetime.timedelta(days=days)
            sub.status = 'ACTIVE'
            sub.save(update_fields=['expires_at', 'status'])
            return APIResponse.success(
                {'expires_at': sub.expires_at, 'status': sub.status},
                message=f'Extended by {days} days.',
            )

        if action == 'cancel':
            sub.status = 'CANCELED'
            sub.auto_renew = False
            sub.save(update_fields=['status', 'auto_renew'])
            return APIResponse.success({'status': sub.status}, message='Subscription canceled.')

        return APIResponse.error('Unknown action.', code='NOT_FOUND', status=404)


class SuperAdminPharmacovigilanceView(APIView):
    """
    GET /api/v1/admin/super/pharmacovigilance/?severity=&reported_to_cdsco=
    Read/triage view over SideEffectReport — severity breakdown + filtered list.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.pharmacovigilance.models import SideEffectReport

        qs = SideEffectReport.objects.select_related(
            'patient__user', 'prescription__medication'
        ).order_by('-created_at')

        severity = request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity.upper())

        cdsco_param = request.query_params.get('reported_to_cdsco')
        if cdsco_param is not None:
            qs = qs.filter(reported_to_cdsco=cdsco_param.lower() == 'true')

        severity_counts = SideEffectReport.objects.aggregate(
            mild=Count('id', filter=Q(severity='MILD')),
            moderate=Count('id', filter=Q(severity='MODERATE')),
            severe=Count('id', filter=Q(severity='SEVERE')),
            life_threatening=Count('id', filter=Q(severity='LIFE_THREATENING')),
            ongoing=Count('id', filter=Q(is_ongoing=True)),
        )

        rows = [
            {
                'id': str(r.id),
                'patient': r.patient.user.full_name,
                'medication': r.prescription.medication.name,
                'symptom': r.symptom,
                'severity': r.severity,
                'onset_at': r.onset_at,
                'is_ongoing': r.is_ongoing,
                'reported_to_doctor': r.reported_to_doctor,
                'reported_to_cdsco': r.reported_to_cdsco,
            }
            for r in qs[:100]
        ]

        return APIResponse.success({
            'severity_counts': severity_counts,
            'rows': rows,
        })


class SuperAdminDeviceFleetView(APIView):
    """
    GET /api/v1/admin/super/devices/
    Fleet-wide device health — beyond the existing Admin "Hardware" page (which only
    covers inventory/ID generation), this shows live online/offline + fault events.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.iot.models import Device, DeviceEvent

        devices = Device.objects.select_related('user').all()
        online_cutoff = timezone.now() - timezone.timedelta(minutes=15)
        total_count = devices.count()
        online_count = devices.filter(last_seen_at__gte=online_cutoff).count()
        low_battery = devices.filter(battery_level__lt=20, battery_level__isnull=False).count()
        faulty = devices.filter(
            Q(stepper_status='error') | Q(servo_status='error') | Q(ultrasonic_status='error')
        ).count()

        recent_faults = DeviceEvent.objects.filter(
            event_type__in=['LOW_BATTERY', 'TAMPER', 'DOSE_TIMEOUT', 'DOSE_MISSED']
        ).select_related('device').order_by('-created_at')[:50]

        return APIResponse.success({
            'summary': {
                'total': total_count,
                'online': online_count,
                'offline': total_count - online_count,
                'low_battery': low_battery,
                'faulty': faulty,
            },
            'devices': [
                {
                    'id': str(d.id),
                    'device_name': d.device_name,
                    'owner_email': d.user.email,
                    'is_online': d.is_online(),
                    'battery_level': d.battery_level,
                    'firmware_version': d.firmware_version,
                    'stepper_status': d.stepper_status,
                    'servo_status': d.servo_status,
                    'ultrasonic_status': d.ultrasonic_status,
                    'last_seen_at': d.last_seen_at,
                }
                for d in devices[:100]
            ],
            'recent_faults': [
                {
                    'id': str(e.id),
                    'device_name': e.device.device_name,
                    'event_type': e.event_type,
                    'occurred_at': e.occurred_at or e.created_at,
                }
                for e in recent_faults
            ],
        })


class SuperAdminNotificationsCenterView(APIView):
    """
    GET /api/v1/admin/super/notifications-center/
    Cross-channel delivery health — extends AdminNotificationDeliveryRatesView (overall
    rate) with a per-channel breakdown plus Telegram bot session/onboarding status.
    (The WhatsApp bot app currently has no models wired up, so only Telegram is shown
    alongside the generic Notification channels; add it here once that app is built out.)
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.notifications.models import Notification

        total = Notification.objects.count()
        delivered = Notification.objects.filter(status='DELIVERED').count()
        failed = Notification.objects.filter(status='FAILED').count()
        overall_rate = round(delivered / total * 100, 2) if total else 0

        by_channel = list(
            Notification.objects.values('channel')
            .annotate(
                total=Count('id'),
                delivered=Count('id', filter=Q(status='DELIVERED')),
                failed=Count('id', filter=Q(status='FAILED')),
            )
            .order_by('channel')
        )
        for row in by_channel:
            row['rate_pct'] = round(row['delivered'] / row['total'] * 100, 2) if row['total'] else 0

        telegram_stats = {'total_sessions': 0, 'onboarded': 0, 'active_24h': None}
        try:
            from apps.telegram_bot.models import TelegramSession
            telegram_stats['total_sessions'] = TelegramSession.objects.count()
            telegram_stats['onboarded'] = TelegramSession.objects.filter(onboarding_done=True).count()
            telegram_stats['active_24h'] = TelegramSession.objects.filter(
                last_activity_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count()
        except Exception:
            pass

        return APIResponse.success({
            'overall': {'total': total, 'delivered': delivered, 'failed': failed, 'rate_pct': overall_rate},
            'by_channel': by_channel,
            'telegram': telegram_stats,
        })


class SuperAdminInsuranceReportsView(APIView):
    """
    GET /api/v1/admin/super/insurance/
    Overview of AdherenceReportShare / ReportAccessLog — how many reports have been
    shared, with whom, and their access history.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.insurance_reports.models import AdherenceReportShare, ReportAccessLog

        shares = AdherenceReportShare.objects.select_related('patient__user').order_by('-created_at')

        by_recipient_type = list(
            shares.values('recipient_type').annotate(count=Count('id')).order_by('recipient_type')
        )
        active_count = shares.filter(is_revoked=False, expires_at__gt=timezone.now()).count()
        revoked_count = shares.filter(is_revoked=True).count()
        expired_count = shares.filter(is_revoked=False, expires_at__lte=timezone.now()).count()

        recent_access = ReportAccessLog.objects.select_related(
            'share__patient__user'
        ).order_by('-accessed_at')[:20]

        return APIResponse.success({
            'summary': {
                'total_shares': shares.count(),
                'active': active_count,
                'revoked': revoked_count,
                'expired': expired_count,
            },
            'by_recipient_type': by_recipient_type,
            'shares': [
                {
                    'id': str(s.id),
                    'patient': s.patient.user.full_name,
                    'recipient_type': s.recipient_type,
                    'recipient_name': s.recipient_name,
                    'expires_at': s.expires_at,
                    'is_revoked': s.is_revoked,
                    'access_count': s.access_count,
                }
                for s in shares[:100]
            ],
            'recent_access': [
                {
                    'id': str(a.id),
                    'patient': a.share.patient.user.full_name,
                    'recipient_name': a.share.recipient_name,
                    'accessor_ip': a.accessor_ip,
                    'accessed_at': a.accessed_at,
                }
                for a in recent_access
            ],
        })


class SuperAdminGamificationView(APIView):
    """
    GET /api/v1/admin/super/gamification/
    Platform-wide view of Streak/Badge/WeeklyAdherenceScore — top streaks, badge
    distribution, and recent weekly engagement trend.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.gamification.models import Streak, Badge, WeeklyAdherenceScore

        top_streaks = Streak.objects.select_related('patient__user').order_by('-current_days')[:20]

        badge_distribution = list(
            Badge.objects.values('badge_type').annotate(count=Count('id')).order_by('-count')
        )

        recent_weeks = (
            WeeklyAdherenceScore.objects.values('week_start')
            .annotate(avg_score=Avg('score'), patients=Count('patient', distinct=True))
            .order_by('-week_start')[:8]
        )

        longest_streak_ever = Streak.objects.order_by('-longest_days').values_list('longest_days', flat=True).first() or 0

        return APIResponse.success({
            'summary': {
                'total_streaks': Streak.objects.filter(current_days__gt=0).count(),
                'total_badges_earned': Badge.objects.count(),
                'longest_streak_ever': longest_streak_ever,
            },
            'top_streaks': [
                {
                    'patient': s.patient.user.full_name,
                    'current_days': s.current_days,
                    'longest_days': s.longest_days,
                }
                for s in top_streaks
            ],
            'badge_distribution': badge_distribution,
            'weekly_trend': list(reversed(recent_weeks)),
        })


class SuperAdminGeofencingView(APIView):
    """
    GET /api/v1/admin/super/geofencing/
    Cross-patient view of GeofenceZone/GeofenceEvent — recent breach (EXIT) events
    across every patient, not scoped to a single caregiver.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.geofence.models import GeofenceZone, GeofenceEvent

        active_zones = GeofenceZone.objects.filter(is_active=True).count()
        total_zones = GeofenceZone.objects.count()

        recent_exits = GeofenceEvent.objects.filter(event_type='EXIT').select_related(
            'patient__user', 'zone'
        ).order_by('-triggered_at')[:50]

        exits_with_pending_dose = GeofenceEvent.objects.filter(
            event_type='EXIT'
        ).exclude(pending_meds=[]).count()

        return APIResponse.success({
            'summary': {
                'active_zones': active_zones,
                'total_zones': total_zones,
                'exits_with_pending_dose': exits_with_pending_dose,
            },
            'recent_exits': [
                {
                    'id': str(e.id),
                    'patient': e.patient.user.full_name,
                    'zone_label': e.zone.label,
                    'triggered_at': e.triggered_at,
                    'pending_meds_count': len(e.pending_meds or []),
                    'alert_sent': e.alert_sent,
                    'call_placed': e.call_placed,
                }
                for e in recent_exits
            ],
        })


class SuperAdminSystemHealthView(APIView):
    """
    GET /api/v1/admin/super/system/
    Lightweight infra/ops view — extends the existing AdminSystemJobsView (Celery Beat)
    with notification failure rate and IoT device connectivity, since there's no
    dedicated APM/infra-metrics model in this codebase yet.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from django_celery_beat.models import PeriodicTask
        from apps.notifications.models import Notification
        from apps.iot.models import Device

        tasks = list(PeriodicTask.objects.values('name', 'enabled', 'last_run_at', 'total_run_count'))
        enabled_count = sum(1 for t in tasks if t['enabled'])

        notif_total = Notification.objects.count()
        notif_failed = Notification.objects.filter(status='FAILED').count()
        notif_error_rate = round(notif_failed / notif_total * 100, 2) if notif_total else 0

        online_cutoff = timezone.now() - timezone.timedelta(minutes=15)
        total_devices = Device.objects.count()
        online_devices = Device.objects.filter(last_seen_at__gte=online_cutoff).count()

        return APIResponse.success({
            'celery': {
                'total_jobs': len(tasks),
                'enabled_jobs': enabled_count,
                'jobs': tasks,
            },
            'notifications': {
                'total': notif_total,
                'failed': notif_failed,
                'error_rate_pct': notif_error_rate,
            },
            'device_connectivity': {
                'total': total_devices,
                'online': online_devices,
                'online_pct': round(online_devices / total_devices * 100, 2) if total_devices else 0,
            },
        })


class SuperAdminAnalyticsView(APIView):
    """
    GET /api/v1/admin/super/analytics/
    Unified cross-cutting insights — built last, pulling a summary metric from every
    other Super Admin page instead of introducing new data sources. Chart-shaped
    (trend series) rather than single numbers, since the per-page endpoints already
    cover the current-state numbers.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.scheduling.models import AdherenceSummary, ReminderJob
        from apps.subscriptions.models import SubscriptionInvoice
        from apps.tenants.models import Tenant
        from apps.gamification.models import Badge
        from apps.iot.models import Device
        from apps.pharmacovigilance.models import SideEffectReport

        fourteen_days_ago = timezone.now() - timezone.timedelta(days=14)
        six_months_ago = timezone.now() - timezone.timedelta(days=180)

        adherence_trend = list(
            AdherenceSummary.objects.filter(period_start__gte=fourteen_days_ago, period_type='daily')
            .values('period_start')
            .annotate(avg_pct=Avg('adherence_pct'))
            .order_by('period_start')
        )

        alert_trend = list(
            ReminderJob.objects.filter(status='MISSED', scheduled_at__gte=fourteen_days_ago)
            .annotate(day=TruncDate('scheduled_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        revenue_trend = list(
            SubscriptionInvoice.objects.filter(status='PAID', paid_at__gte=six_months_ago)
            .annotate(month=TruncMonth('paid_at'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )

        tenant_growth = list(
            Tenant.objects.filter(created_at__gte=six_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        online_cutoff = timezone.now() - timezone.timedelta(minutes=15)
        total_devices = Device.objects.count()
        online_devices = Device.objects.filter(last_seen_at__gte=online_cutoff).count()

        return APIResponse.success({
            'adherence_trend': [
                {'date': r['period_start'], 'avg_pct': round(float(r['avg_pct'] or 0), 2)}
                for r in adherence_trend
            ],
            'alert_volume_trend': [
                {'date': r['day'], 'count': r['count']} for r in alert_trend
            ],
            'revenue_trend': [
                {'month': r['month'], 'total': str(r['total'] or 0)} for r in revenue_trend
            ],
            'tenant_growth': [
                {'month': r['month'], 'count': r['count']} for r in tenant_growth
            ],
            'snapshot': {
                'device_fleet_health_pct': round(online_devices / total_devices * 100, 2) if total_devices else 0,
                'total_badges_earned': Badge.objects.count(),
                'total_tenants': Tenant.objects.count(),
                'open_safety_reports': SideEffectReport.objects.filter(is_ongoing=True).count(),
            },
        })
