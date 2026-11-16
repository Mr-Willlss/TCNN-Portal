from django.shortcuts import render

from accounts.decorators import role_required
from accounts.models import User


@role_required(User.Role.ICT)
def ict_home(request):
    return render(request, 'portal/dashboard.html', {'heading': 'ICT'})


@role_required(User.Role.STUDENT)
def student_home(request):
    return render(request, 'portal/dashboard.html', {'heading': 'Student'})


@role_required(User.Role.LIBRARY, User.Role.ICT)
def library_home(request):
    return render(request, 'portal/dashboard.html', {'heading': 'Library'})
