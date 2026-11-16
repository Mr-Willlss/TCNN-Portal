from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse


class PasswordChangeRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and user.must_change_password
            and request.path != reverse('password_change')
            and request.path != reverse('logout')
            and not self._is_static_or_media(request.path)
        ):
            return redirect('password_change')
        return self.get_response(request)

    @staticmethod
    def _is_static_or_media(path):
        for url in (settings.STATIC_URL, settings.MEDIA_URL):
            prefix = f'/{urlsplit(url).path.lstrip("/")}'.rstrip('/')
            if prefix and (path == prefix or path.startswith(f'{prefix}/')):
                return True
        return False


class FirstRunSetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        User = get_user_model()
        if not User.objects.filter(role=User.Role.ICT).exists():
            if request.path != '/setup/' and not self._is_static_or_media(request.path):
                return redirect('setup')
        return self.get_response(request)

    @staticmethod
    def _is_static_or_media(path):
        for url in (settings.STATIC_URL, settings.MEDIA_URL):
            prefix = f'/{urlsplit(url).path.lstrip("/")}'.rstrip('/')
            if prefix and (path == prefix or path.startswith(f'{prefix}/')):
                return True
        return False
