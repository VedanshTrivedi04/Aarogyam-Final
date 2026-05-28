"""
apps/identity/views/auth.py — Authentication views.
"""

import os
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.utils import timezone

from django.conf import settings
from shared.response import APIResponse
from ..serializers import (
    RegisterSerializer, LoginSerializer, MFAVerifySerializer,
    PasswordChangeSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, MFASetupResponseSerializer,
    MFAVerifyInputSerializer, VerifyEmailSerializer, GoogleAuthSerializer,
)
from ..services import (
    UserRegistrationService, AuthService, MFAService,
    PasswordService, VerificationService, OTPService
)
from ..models import User


# ─── Registration ─────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key='ip', rate='3/h', method='POST', block=True), name='post')
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        try:
            user = UserRegistrationService.register(**s.validated_data)
        except Exception as e:
            return APIResponse.error(str(e), code='REGISTRATION_FAILED')

        return APIResponse.created({
            'user_id': str(user.id),
            'email':   user.email,
            'message': 'Account created. Please verify your email to continue.',
        })


# ─── Login ────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key='ip', rate='5/5m', method='POST', block=True), name='post')
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = LoginSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        try:
            result = AuthService.authenticate(
                email=s.validated_data['email'],
                password=s.validated_data['password'],
                request=request,
            )
        except ValueError as e:
            return APIResponse.error(str(e), code='AUTH_FAILED', status=401)

        if result.get('mfa_required'):
            return APIResponse.success(
                {'mfa_required': True, 'user_id': result['user_id']},
                message='MFA verification required.'
            )

        return APIResponse.success(result, message='Login successful.')


# ─── Logout ───────────────────────────────────────────────────────────────────

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            raw_refresh = request.data.get('refresh')
            if raw_refresh:
                token = RefreshToken(raw_refresh)
                AuthService.logout(str(token['jti']), reason='user_logout')
                token.blacklist()
        except TokenError:
            pass
        return APIResponse.success(message='Logged out successfully.')


# ─── Token Refresh ────────────────────────────────────────────────────────────

class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.data.get('refresh')
        if not raw_refresh:
            return APIResponse.error('Refresh token is required.', code='TOKEN_MISSING')
        try:
            token  = RefreshToken(raw_refresh)
            access = str(token.access_token)
            return APIResponse.success({'access': access})
        except TokenError as e:
            return APIResponse.error(str(e), code='TOKEN_INVALID', status=401)


# ─── Password ─────────────────────────────────────────────────────────────────

class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = PasswordChangeSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        try:
            PasswordService.change_password(
                request.user,
                s.validated_data['old_password'],
                s.validated_data['new_password'],
            )
        except Exception as e:
            return APIResponse.error(str(e))
        return APIResponse.success(message='Password changed. All sessions revoked.')


@method_decorator(ratelimit(key='post:email', rate='3/h', method='POST', block=True), name='post')
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        PasswordService.send_reset_email(s.validated_data['email'])
        return APIResponse.success(message='If this email is registered, a reset link has been sent.')


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def put(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        try:
            PasswordService.confirm_reset(s.validated_data['token'], s.validated_data['new_password'])
        except Exception as e:
            return APIResponse.error(str(e))
        return APIResponse.success(message='Password reset successfully. Please log in.')


# ─── MFA ──────────────────────────────────────────────────────────────────────

class MFASetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Generate TOTP secret + QR code for setup."""
        result = MFAService.setup_totp(request.user)
        return APIResponse.success(result, message='Scan the QR code in your authenticator app, then verify.')


@method_decorator(ratelimit(key='user', rate='10/5m', method='POST', block=True), name='post')
class MFAVerifyView(APIView):
    permission_classes = [AllowAny]  # called before JWT is issued

    def post(self, request):
        """Verify MFA code and issue JWT tokens."""
        s = MFAVerifySerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        try:
            user = User.objects.get(id=s.validated_data['user_id'], is_active=True)
        except User.DoesNotExist:
            return APIResponse.error('User not found.', code='NOT_FOUND', status=404)

        try:
            tokens = MFAService.complete_mfa_login(user, s.validated_data['code'], request)
        except ValueError as e:
            return APIResponse.error(str(e), code='MFA_FAILED', status=401)

        return APIResponse.success(tokens, message='MFA verified. Login successful.')


class MFABackupCodesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Regenerate backup codes (shown once)."""
        codes = MFAService.generate_backup_codes(request.user)
        return APIResponse.success(
            {'backup_codes': codes},
            message='Store these codes safely. They will not be shown again.'
        )


# ─── Email Verification ───────────────────────────────────────────────────────

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = VerifyEmailSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        
        success = VerificationService.verify_email(s.validated_data['token'])
        if not success:
            return APIResponse.error('Invalid or expired token.', code='INVALID_TOKEN', status=400)
            
        return APIResponse.success(message='Email verified successfully. You can now log in.')


# ─── Google OAuth ─────────────────────────────────────────────────────────────

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = GoogleAuthSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)
        
        credential = s.validated_data['credential']
        
        try:
            from google.oauth2 import id_token
            from google.auth.transport.requests import Request
            
            client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
            if not client_id:
                client_id = os.environ.get('GOOGLE_CLIENT_ID')
                
            # Verify the ID token
            id_info = id_token.verify_oauth2_token(credential, Request(), client_id)
            
            if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')

            # ID token is valid. Get or create user.
            email = id_info['email']
            full_name = id_info.get('name', email.split('@')[0])
            
            result = AuthService.login_social(email, full_name, provider='GOOGLE', request=request)
            return APIResponse.success(result, message='Google login successful.')
            
        except Exception as e:
            return APIResponse.error(f'Google authentication failed: {str(e)}', code='GOOGLE_AUTH_FAILED', status=400)


# ─── OTP Login ────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key='post:email', rate='5/10m', method='POST', block=True), name='post')
class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return APIResponse.error('Email is required.', code='VALIDATION_ERROR')
        
        try:
            OTPService.send_otp(email)
        except ValueError as e:
            return APIResponse.error(str(e), code='EMAIL_FAILED', status=400)
            
        return APIResponse.success(message='If this email is registered, an OTP has been sent.')


@method_decorator(ratelimit(key='ip', rate='10/5m', method='POST', block=True), name='post')
class LoginWithOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        otp   = request.data.get('otp', '').strip()
        if not email or not otp:
            return APIResponse.error('Email and OTP are required.', code='VALIDATION_ERROR')
        try:
            result = OTPService.verify_otp_and_login(email, otp, request)
        except ValueError as e:
            return APIResponse.error(str(e), code='OTP_FAILED', status=401)
        return APIResponse.success(result, message='Login successful.')
