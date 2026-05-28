"""
shared/exceptions.py — Standardized exception handler for DRF.
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from .response import APIResponse

def custom_exception_handler(exc, context):
    """
    Catch DRF exceptions and convert them to our standard APIResponse format.
    """
    import traceback
    print("DEBUG EXCEPTION:", type(exc), exc)
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    
    response = exception_handler(exc, context)

    if response is not None:
        # Standard DRF exceptions (ValidationError, PermissionDenied, etc.)
        errors = response.data if isinstance(response.data, dict) else {'detail': response.data}
        return APIResponse.error(
            message=str(errors.get('detail', 'An error occurred.')),
            code=getattr(exc, 'default_code', 'ERROR'),
            status=response.status_code,
            errors=errors
        )

    # Let Django handle 500s or other uncaught exceptions.
    return None

class InvalidInviteTokenError(APIException):
    status_code = 400
    default_detail = 'The provided invitation token is invalid or has expired.'
    default_code = 'invalid_invite_token'
class SubscriptionLimitError(APIException):
    status_code = 402
    default_detail = 'Subscription limit exceeded or feature not available on current plan.'
    default_code = 'subscription_limit_exceeded'
