"""
apps/identity/services.py — Business logic for auth, MFA, sessions.
"""
import hashlib
import secrets
import pyotp
import qrcode
import io
import base64
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserSession, MFAConfig, NotificationPreferences, UserDevice
from shared.middleware import get_client_ip


class UserRegistrationService:
    """Handles new user registration with all required linked objects."""

    @staticmethod
    def register(email: str, password: str, full_name: str,
                 role: str = 'PATIENT', phone_number: str = None) -> User:
        if User.objects.filter(email__iexact=email).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'email': 'An account with this email already exists.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            phone_number=phone_number,
        )

        # Create linked preference objects
        MFAConfig.objects.create(user=user)
        NotificationPreferences.objects.create(user=user)

        # Assign free subscription plan
        UserRegistrationService._assign_free_plan(user)

        # Broadcast via AgentOrchestrator
        try:
            from agenthandover import get_orchestrator
            orchestrator = get_orchestrator()
            orchestrator.broadcast('USER_REGISTERED', {
                'user_id': str(user.id), 'email': user.email, 'role': user.role
            })
        except Exception:
            pass  # Non-blocking — registration still succeeds

        # Auto-create role profile so downstream queries always find one
        try:
            if user.role == 'PATIENT':
                from apps.clinical.models import Patient
                Patient.objects.get_or_create(user=user)
            elif user.role == 'CAREGIVER':
                from apps.clinical.models import Caregiver
                Caregiver.objects.get_or_create(user=user)
        except Exception:
            pass  # Non-blocking — profile creation failure doesn't break registration

        # Generate Verification Token
        VerificationService.send_verification_email(user)

        return user

    @staticmethod
    def _assign_free_plan(user: User):
        try:
            from apps.subscriptions.models import SubscriptionPlan, UserSubscription
            plan, _ = SubscriptionPlan.objects.get_or_create(
                slug='free',
                defaults={'name': 'Free', 'price_monthly': 0, 'price_yearly': 0, 'features': {}}
            )
            UserSubscription.objects.create(
                user=user,
                plan=plan,
                status='ACTIVE',
                started_at=timezone.now(),
            )
        except Exception:
            pass


class AuthService:
    """Handles login, session creation, and token generation."""

    @staticmethod
    def authenticate(email: str, password: str, request=None) -> dict:
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise ValueError('Invalid email or password.')

        if not user.is_active:
            raise ValueError('This account has been deactivated.')

        if user.is_locked:
            raise ValueError(f'Account locked. Try again after {user.locked_until.strftime("%H:%M UTC")}.')

        if not user.check_password(password):
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.locked_until = timezone.now() + timedelta(minutes=15)
            user.save(update_fields=['failed_login_count', 'locked_until'])
            raise ValueError('Invalid email or password.')

        if not user.is_email_verified:
            # We can allow login if verified is not mandatory, but usually it is for sensitive apps.
            # For now, let's just warn or block.
            raise ValueError('Please verify your email address before logging in.')

        # Reset failed count on success
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_ip = get_client_ip(request) if request else None
        user.save(update_fields=['failed_login_count', 'locked_until', 'last_login_ip'])

        # Check if MFA is required
        if user.mfa_enabled:
            return {'mfa_required': True, 'user_id': str(user.id)}

        return AuthService._issue_tokens(user, request)

    @staticmethod
    def _issue_tokens(user: User, request=None) -> dict:
        refresh = RefreshToken.for_user(user)
        jti     = str(refresh['jti'])

        # Persist session
        UserSession.objects.create(
            user=user,
            jti=jti,
            refresh_token_hash=hashlib.sha256(str(refresh).encode()).hexdigest(),
            device_type=request.META.get('HTTP_X_DEVICE_TYPE', 'unknown') if request else 'unknown',
            device_name=request.META.get('HTTP_X_DEVICE_NAME') if request else None,
            app_version=request.META.get('HTTP_X_APP_VERSION') if request else None,
            ip_address=get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            expires_at=timezone.now() + timedelta(days=30),
        )

        return {
            'mfa_required': False,
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id':       str(user.id),
                'email':    user.email,
                'full_name': user.full_name,
                'role':     user.role,
                'mfa_enabled': user.mfa_enabled,
                'plan':     user.get_plan_slug(),
            }
        }

    @staticmethod
    def logout(jti: str, reason: str = 'user_logout'):
        UserSession.objects.filter(jti=jti, revoked_at__isnull=True).update(
            revoked_at=timezone.now(), revoke_reason=reason
        )

    @staticmethod
    def revoke_all_sessions(user: User, reason: str = 'password_change'):
        UserSession.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=timezone.now(), revoke_reason=reason
        )

    @staticmethod
    def login_social(email: str, full_name: str, provider: str, request=None) -> dict:
        """Finds or creates a user via social provider and issues tokens."""
        user = User.objects.filter(email__iexact=email).first()
        
        if not user:
            # Create new user if not exists
            user = UserRegistrationService.register(
                email=email,
                password=secrets.token_urlsafe(16), # Random password for social users
                full_name=full_name,
                role='PATIENT', # Default role
            )
            # Social login accounts are usually considered verified
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified', 'updated_at'])
        else:
            if not user.is_active:
                raise ValueError('This account has been deactivated.')
            
            # Ensure social users are verified
            if not user.is_email_verified:
                user.is_email_verified = True
                user.save(update_fields=['is_email_verified', 'updated_at'])

        if user.mfa_enabled:
            return {'mfa_required': True, 'user_id': str(user.id)}

        return AuthService._issue_tokens(user, request)


class MFAService:
    """Handles TOTP setup, verification, and backup codes."""

    @staticmethod
    def setup_totp(user: User) -> dict:
        config, _ = MFAConfig.objects.get_or_create(user=user)
        secret = pyotp.random_base32()
        config.totp_secret = secret  # encrypted by EncryptedCharField
        config.save(update_fields=['totp_secret', 'updated_at'])

        totp = pyotp.TOTP(secret)
        uri  = totp.provisioning_uri(name=user.email, issuer_name='MedAdhere')

        # Generate QR code as base64
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_base64 = base64.b64encode(buf.getvalue()).decode()

        return {'secret': secret, 'qr_code': f'data:image/png;base64,{qr_base64}', 'uri': uri}

    @staticmethod
    def verify_totp(user: User, code: str) -> bool:
        try:
            config = user.mfa_config
            if not config.totp_secret:
                return False
            totp = pyotp.TOTP(config.totp_secret)
            if totp.verify(code, valid_window=1):
                if not config.is_totp_enabled:
                    config.is_totp_enabled = True
                    user.mfa_enabled = True
                    config.save(update_fields=['is_totp_enabled', 'updated_at'])
                    user.save(update_fields=['mfa_enabled', 'updated_at'])
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def generate_backup_codes(user: User) -> list:
        codes   = [secrets.token_hex(5).upper() for _ in range(10)]
        hashed  = [make_password(c) for c in codes]
        user.mfa_config.backup_codes = hashed
        user.mfa_config.save(update_fields=['backup_codes', 'updated_at'])
        return codes   # plain codes shown once

    @staticmethod
    def verify_backup_code(user: User, code: str) -> bool:
        try:
            config = user.mfa_config
            for i, hashed in enumerate(config.backup_codes):
                if check_password(code.upper(), hashed):
                    # Consume the code (one-time use)
                    config.backup_codes.pop(i)
                    config.save(update_fields=['backup_codes', 'updated_at'])
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def complete_mfa_login(user: User, code: str, request=None) -> dict:
        """Validate MFA code and issue JWT tokens."""
        if not (MFAService.verify_totp(user, code) or MFAService.verify_backup_code(user, code)):
            raise ValueError('Invalid MFA code. Please try again.')
        return AuthService._issue_tokens(user, request)


class PasswordService:
    """Handles password changes and reset flows."""

    @staticmethod
    def change_password(user: User, old_password: str, new_password: str):
        if not user.check_password(old_password):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'old_password': 'Current password is incorrect.'})
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.save(update_fields=['password', 'password_changed_at', 'updated_at'])
        AuthService.revoke_all_sessions(user, reason='password_change')

    @staticmethod
    def send_reset_email(email: str):
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
            token = secrets.token_urlsafe(48)
            from django.core.cache import cache
            cache.set(f'pwd_reset:{token}', str(user.id), timeout=3600)  # 1 hr TTL
            
            # Send email via background task
            try:
                from .tasks import send_password_reset_email_task
                send_password_reset_email_task.delay(str(user.id), token)
            except Exception:
                pass
        except User.DoesNotExist:
            pass  # Don't reveal whether email exists

    @staticmethod
    def confirm_reset(token: str, new_password: str):
        from django.core.cache import cache
        user_id = cache.get(f'pwd_reset:{token}')
        if not user_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'token': 'Reset token is invalid or has expired.'})
        user = User.objects.get(id=user_id)
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.save(update_fields=['password', 'password_changed_at', 'updated_at'])
        cache.delete(f'pwd_reset:{token}')
        AuthService.revoke_all_sessions(user, reason='password_reset')


class OTPService:
    """Handles email-based OTP login."""

    TTL = 300  # 5 minutes

    @staticmethod
    def send_otp(email: str):
        """Generate a 6-digit OTP, cache it, and email it with HTML template."""
        import random
        from django.core.cache import cache
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.conf import settings

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return  # don't reveal whether email exists

        otp = str(random.randint(100000, 999999))
        cache.set(f'login_otp:{email.lower()}', otp, timeout=OTPService.TTL)

        try:
            html_body = render_to_string('emails/otp_email.html', {'otp': otp})
            plain_body = (
                f'Your Aarogyam one-time login code is: {otp}\n\n'
                f'This code expires in 5 minutes. Do not share it with anyone.'
            )
            msg = EmailMultiAlternatives(
                subject='Your Aarogyam Login OTP',
                body=plain_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send(fail_silently=False)
        except Exception as e:
            # Throwing the exact error so it can be seen in server logs and API response
            raise ValueError(f"Email sending failed: {str(e)}")

    @staticmethod
    def verify_otp_and_login(email: str, otp: str, request=None) -> dict:
        """Verify OTP and issue JWT tokens."""
        from django.core.cache import cache

        stored = cache.get(f'login_otp:{email.lower()}')
        if not stored or stored != otp.strip():
            raise ValueError('Invalid or expired OTP. Please request a new one.')

        cache.delete(f'login_otp:{email.lower()}')

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            raise ValueError('User not found.')

        if user.is_locked:
            raise ValueError(f'Account locked. Try again after {user.locked_until.strftime("%H:%M UTC")}.')

        return AuthService._issue_tokens(user, request)


class VerificationService:
    """Handles email and phone verification flows."""

    @staticmethod
    def send_verification_email(user: User):
        token = secrets.token_urlsafe(48)
        from django.core.cache import cache
        # Store user_id for 24 hours
        cache.set(f'email_verify:{token}', str(user.id), timeout=86400)
        
        # Trigger verification email task
        try:
            from .tasks import send_verification_email_task
            send_verification_email_task.delay(str(user.id), token)
        except Exception:
            pass

    @staticmethod
    def verify_email(token: str) -> bool:
        from django.core.cache import cache
        user_id = cache.get(f'email_verify:{token}')
        if not user_id:
            return False
            
        try:
            user = User.objects.get(id=user_id)
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified', 'updated_at'])
            cache.delete(f'email_verify:{token}')
            return True
        except User.DoesNotExist:
            return False
