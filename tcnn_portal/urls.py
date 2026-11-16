from django.contrib.auth.views import LogoutView
from django.urls import path

from accounts import views as account_views
from portal import ict_views
from portal import views as portal_views

urlpatterns = [
    path('setup/', account_views.first_run_setup, name='setup'),
    path('accounts/login/', account_views.RoleLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path(
        'accounts/password-change/',
        account_views.RequiredPasswordChangeView.as_view(),
        name='password_change',
    ),
    path('no-screen/', account_views.no_screen, name='no_screen'),
    path('ict/', portal_views.ict_home, name='ict_home'),
    path('ict/programs/', ict_views.ict_programs, name='ict_programs'),
    path('ict/programs/add/', ict_views.ict_program_add, name='ict_program_add'),
    path(
        'ict/programs/<int:program_id>/edit/',
        ict_views.ict_program_edit,
        name='ict_program_edit',
    ),
    path('ict/staff/', ict_views.ict_staff, name='ict_staff'),
    path('ict/staff/add/', ict_views.ict_staff_add, name='ict_staff_add'),
    path(
        'ict/staff/<int:user_id>/edit/',
        ict_views.ict_staff_edit,
        name='ict_staff_edit',
    ),
    path(
        'ict/staff/<int:user_id>/deactivate/',
        ict_views.ict_staff_deactivate,
        name='ict_staff_deactivate',
    ),
    path(
        'ict/staff/<int:user_id>/reactivate/',
        ict_views.ict_staff_reactivate,
        name='ict_staff_reactivate',
    ),
    path(
        'ict/staff/<int:user_id>/reset-password/',
        ict_views.ict_staff_reset_password,
        name='ict_staff_reset_password',
    ),
    path('student/', portal_views.student_home, name='student_home'),
    path('library/', portal_views.library_home, name='library_home'),
]
