from django.shortcuts import render

from accounts.decorators import role_required
from accounts.models import User
from .models import Program, StudentProfile


@role_required(User.Role.ICT)
def ict_home(request):
    return render(
        request,
        'portal/dashboard.html',
        {
            'heading': 'ICT',
            'active_students': StudentProfile.objects.filter(
                status=StudentProfile.Status.ACTIVE,
                user__is_active=True,
            ).count(),
            'active_staff': User.objects.filter(
                role__in=[
                    User.Role.ICT,
                    User.Role.LIBRARY,
                    User.Role.BURSARY,
                    User.Role.REGISTRY,
                    User.Role.CLINIC,
                ],
                is_active=True,
            ).count(),
            'program_count': Program.objects.count(),
        },
    )


@role_required(User.Role.STUDENT)
def student_home(request):
    return render(request, 'portal/dashboard.html', {'heading': 'Student'})


@role_required(User.Role.LIBRARY, User.Role.ICT)
def library_home(request):
    return render(request, 'portal/dashboard.html', {'heading': 'Library'})
