from django.contrib.auth.views import LogoutView
from django.urls import path

from accounts import views as account_views
from portal import views as portal_views

urlpatterns = [
    path('setup/', account_views.first_run_setup, name='setup'),
    path('accounts/login/', account_views.RoleLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('no-screen/', account_views.no_screen, name='no_screen'),
    path('ict/', portal_views.ict_home, name='ict_home'),
    path('student/', portal_views.student_home, name='student_home'),
    path('library/', portal_views.library_home, name='library_home'),
]
