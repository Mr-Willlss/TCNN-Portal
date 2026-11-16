from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden


def role_required(*allowed_roles):
    if not allowed_roles:
        raise ValueError('At least one allowed role must be provided.')

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            if request.user.role not in allowed_roles:
                return HttpResponseForbidden()
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
