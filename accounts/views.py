from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from portal.models import AuditLog

from .forms import InitialICTSetupForm


class RoleLoginView(LoginView):
    template_name = 'accounts/login.html'

    def get_success_url(self):
        role_urls = {
            get_user_model().Role.ICT: 'ict_home',
            get_user_model().Role.STUDENT: 'student_home',
            get_user_model().Role.LIBRARY: 'library_home',
        }
        return reverse(role_urls.get(self.request.user.role, 'no_screen'))


@require_http_methods(['GET', 'POST'])
def first_run_setup(request):
    User = get_user_model()
    if User.objects.filter(role=User.Role.ICT).exists():
        raise Http404

    form = InitialICTSetupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            if User.objects.filter(role=User.Role.ICT).exists():
                raise Http404
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                password=form.cleaned_data['password1'],
                role=User.Role.ICT,
                is_active=True,
            )
            AuditLog.objects.create(
                actor=None,
                action='create',
                target_type='User',
                target_id=str(user.pk),
                old_value='',
                new_value=f'username={user.username}; role={user.role}; is_active={user.is_active}',
            )
        return redirect('login')

    return render(request, 'accounts/setup.html', {'form': form})


@login_required
def no_screen(request):
    return render(request, 'accounts/no_screen.html')
