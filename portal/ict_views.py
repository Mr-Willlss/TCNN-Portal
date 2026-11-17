from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required

from .forms import (
    ProgramForm,
    StaffCreateForm,
    StaffEditForm,
    StudentCreateForm,
    StudentEditForm,
    StudentPasswordResetForm,
    TemporaryPasswordForm,
)
from .models import AuditLog, Program, StudentProfile


User = get_user_model()


def _staff_queryset():
    staff_roles = [role for role, _label in User.Role.choices if role != User.Role.STUDENT]
    return User.objects.filter(role__in=staff_roles)


def _staff_values(user):
    return (
        f'username={user.username}; first_name={user.first_name}; '
        f'last_name={user.last_name}; role={user.role}; is_active={user.is_active}; '
        f'must_change_password={user.must_change_password}'
    )


def _audit(actor, action, target_type, target_id, old_value, new_value):
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        old_value=old_value,
        new_value=new_value,
    )


def _program_values(program):
    return (
        f'name={program.name}; code={program.code}; '
        f'duration_years={program.duration_years}'
    )


def _student_values(profile):
    photo = profile.passport_photo.name if profile.passport_photo else ''
    return (
        f'username={profile.user.username}; first_name={profile.user.first_name}; '
        f'last_name={profile.user.last_name}; matric_number={profile.matric_number}; '
        f'program={profile.program.code}; year_of_study={profile.year_of_study}; '
        f'status={profile.status}; clinic_clearance={profile.clinic_clearance}; '
        f'is_active={profile.user.is_active}; passport_photo={photo}'
    )


def _student_list_context(request, reset_form=None, reset_profile_id=None):
    query = request.GET.get('q', request.POST.get('q', '')).strip()
    program_filter = request.GET.get('program', request.POST.get('program', ''))
    status_filter = request.GET.get('status', request.POST.get('status', ''))
    students = StudentProfile.objects.select_related('user', 'program').all()
    if query:
        terms = query.split()
        search = (
            Q(matric_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        )
        if len(terms) > 1:
            search |= (
                Q(user__first_name__icontains=terms[0])
                & Q(user__last_name__icontains=' '.join(terms[1:]))
            ) | (
                Q(user__last_name__icontains=terms[0])
                & Q(user__first_name__icontains=' '.join(terms[1:]))
            )
        students = students.filter(search)
    if program_filter.isdigit():
        students = students.filter(program_id=program_filter)
    status_choices = dict(StudentProfile.Status.choices)
    if status_filter in status_choices:
        students = students.filter(status=status_filter)

    page_obj = Paginator(
        students.order_by('matric_number', 'pk'),
        25,
    ).get_page(request.GET.get('page', request.POST.get('page')))
    return {
        'page_obj': page_obj,
        'students': page_obj.object_list,
        'programs': Program.objects.order_by('name', 'code'),
        'query': query,
        'program_filter': program_filter,
        'status_filter': status_filter,
        'status_choices': StudentProfile.Status.choices,
        'reset_form': reset_form,
        'reset_profile_id': reset_profile_id,
    }


@role_required(User.Role.ICT)
def ict_students(request):
    return render(
        request,
        'portal/ict/student_list.html',
        _student_list_context(request),
    )


@role_required(User.Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_student_add(request):
    form = StudentCreateForm(
        request.POST or None,
        request.FILES or None,
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = User.objects.create_user(
                username=form.cleaned_data['matric_number'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role=User.Role.STUDENT,
                password=form.cleaned_data['temporary_password'],
                must_change_password=True,
            )
            profile = StudentProfile(
                user=user,
                matric_number=form.cleaned_data['matric_number'],
                program=form.cleaned_data['program'],
                year_of_study=form.cleaned_data['year_of_study'],
                passport_photo=form.cleaned_data.get('passport_photo'),
            )
            profile.save()
            _audit(request.user, 'create', 'StudentProfile', profile.pk, '', _student_values(profile))
        return redirect('ict_students')
    return render(request, 'portal/ict/student_form.html', {
        'form': form,
        'heading': 'Add student',
    })


@role_required(User.Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_student_edit(request, student_id):
    profile = get_object_or_404(
        StudentProfile.objects.select_related('user', 'program'),
        pk=student_id,
    )
    form = StudentEditForm(
        request.POST or None,
        request.FILES or None,
        profile=profile,
        initial={
            'first_name': profile.user.first_name,
            'last_name': profile.user.last_name,
            'matric_number': profile.matric_number,
            'program': profile.program_id,
            'year_of_study': profile.year_of_study,
        },
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            profile = get_object_or_404(
                StudentProfile.objects.select_for_update().select_related('user', 'program'),
                pk=student_id,
            )
            old_value = _student_values(profile)
            old_photo = profile.passport_photo.name if profile.passport_photo else ''
            user = profile.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.username = form.cleaned_data['matric_number']
            user.save(update_fields=['first_name', 'last_name', 'username'])

            profile.matric_number = form.cleaned_data['matric_number']
            profile.program = form.cleaned_data['program']
            profile.year_of_study = form.cleaned_data['year_of_study']
            if form.cleaned_data.get('passport_photo'):
                profile.passport_photo = form.cleaned_data['passport_photo']
            profile.save()
            new_value = _student_values(profile)
            _audit(request.user, 'edit', 'StudentProfile', profile.pk, old_value, new_value)

            new_photo = profile.passport_photo.name if profile.passport_photo else ''
            if old_photo != new_photo:
                _audit(
                    request.user,
                    'photo_change',
                    'StudentProfile',
                    profile.pk,
                    f'passport_photo={old_photo}',
                    f'passport_photo={new_photo}',
                )
                if old_photo:
                    storage = profile.passport_photo.storage
                    transaction.on_commit(
                        lambda storage=storage, name=old_photo: storage.delete(name)
                    )
        return redirect('ict_students')
    return render(request, 'portal/ict/student_form.html', {
        'form': form,
        'heading': 'Edit student',
        'profile': profile,
    })


@role_required(User.Role.ICT)
@require_POST
def ict_student_deactivate(request, student_id):
    with transaction.atomic():
        profile = get_object_or_404(
            StudentProfile.objects.select_for_update().select_related('user', 'program'),
            pk=student_id,
        )
        old_value = _student_values(profile)
        profile.status = StudentProfile.Status.DEACTIVATED
        profile.user.is_active = False
        profile.user.save(update_fields=['is_active'])
        profile.save(update_fields=['status'])
        _audit(
            request.user,
            'deactivate',
            'StudentProfile',
            profile.pk,
            old_value,
            _student_values(profile),
        )
    return redirect('ict_students')


@role_required(User.Role.ICT)
@require_POST
def ict_student_reactivate(request, student_id):
    with transaction.atomic():
        profile = get_object_or_404(
            StudentProfile.objects.select_for_update().select_related('user', 'program'),
            pk=student_id,
        )
        old_value = _student_values(profile)
        profile.status = StudentProfile.Status.ACTIVE
        profile.user.is_active = True
        profile.user.save(update_fields=['is_active'])
        profile.save(update_fields=['status'])
        _audit(
            request.user,
            'reactivate',
            'StudentProfile',
            profile.pk,
            old_value,
            _student_values(profile),
        )
    return redirect('ict_students')


@role_required(User.Role.ICT)
@require_POST
def ict_student_reset_password(request, student_id):
    profile = get_object_or_404(
        StudentProfile.objects.select_related('user'),
        pk=student_id,
    )
    form = StudentPasswordResetForm(request.POST, profile=profile)
    if form.is_valid():
        with transaction.atomic():
            old_value = f'must_change_password={profile.user.must_change_password}'
            profile.user.set_password(form.cleaned_data['password1'])
            profile.user.must_change_password = True
            profile.user.save(update_fields=['password', 'must_change_password'])
            _audit(
                request.user,
                'password_reset',
                'StudentProfile',
                profile.pk,
                old_value,
                'temporary_password_set=True; must_change_password=True',
            )
        return redirect('ict_students')
    return render(
        request,
        'portal/ict/student_list.html',
        _student_list_context(request, form, profile.pk),
    )


@role_required(get_user_model().Role.ICT)
def ict_programs(request):
    return render(request, 'portal/ict/program_list.html', {
        'programs': Program.objects.order_by('name', 'code'),
    })


@role_required(get_user_model().Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_program_add(request):
    form = ProgramForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            program = form.save()
            _audit(request.user, 'create', 'Program', program.pk, '', _program_values(program))
        return redirect('ict_programs')
    return render(request, 'portal/ict/program_form.html', {
        'form': form,
        'heading': 'Add program',
    })


@role_required(get_user_model().Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_program_edit(request, program_id):
    program = get_object_or_404(Program, pk=program_id)
    form = ProgramForm(request.POST or None, instance=program)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            old_value = _program_values(program)
            program = form.save()
            _audit(
                request.user,
                'edit',
                'Program',
                program.pk,
                old_value,
                _program_values(program),
            )
        return redirect('ict_programs')
    return render(request, 'portal/ict/program_form.html', {
        'form': form,
        'heading': 'Edit program',
        'program': program,
    })


@role_required(get_user_model().Role.ICT)
def ict_staff(request):
    query = request.GET.get('q', '').strip()
    staff = _staff_queryset()
    if query:
        terms = query.split()
        search = (
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
        if len(terms) > 1:
            search |= (
                Q(first_name__icontains=terms[0])
                & Q(last_name__icontains=' '.join(terms[1:]))
            ) | (
                Q(last_name__icontains=terms[0])
                & Q(first_name__icontains=' '.join(terms[1:]))
            )
        staff = staff.filter(search)
    return render(request, 'portal/ict/staff_list.html', {
        'staff': staff.order_by('last_name', 'first_name', 'username'),
        'query': query,
    })


@role_required(get_user_model().Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_staff_add(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        User = get_user_model()
        with transaction.atomic():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role=form.cleaned_data['role'],
                password=form.cleaned_data['password1'],
                must_change_password=True,
            )
            _audit(request.user, 'create', 'User', user.pk, '', _staff_values(user))
        return redirect('ict_staff')
    return render(request, 'portal/ict/staff_form.html', {
        'form': form,
        'heading': 'Add staff account',
    })


@role_required(get_user_model().Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_staff_edit(request, user_id):
    User = get_user_model()
    user = get_object_or_404(_staff_queryset(), pk=user_id)
    form = StaffEditForm(request.POST or None, initial={
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
    })
    if request.method == 'POST' and form.is_valid():
        new_role = form.cleaned_data['role']
        if user.pk == request.user.pk and new_role != user.role:
            return HttpResponseForbidden('You cannot change your own role.')

        with transaction.atomic():
            user = get_object_or_404(
                User.objects.select_for_update(),
                pk=user.pk,
                role__in=[role for role, _label in User.Role.choices
                          if role != User.Role.STUDENT],
            )
            old_value = _staff_values(user)
            old_role = user.role
            if (
                user.is_active
                and old_role == User.Role.ICT
                and new_role != User.Role.ICT
                and User.objects.filter(role=User.Role.ICT, is_active=True).count() <= 1
            ):
                return HttpResponseForbidden('The last active ICT user cannot be demoted.')

            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.role = new_role
            user.save(update_fields=['first_name', 'last_name', 'role'])
            new_value = _staff_values(user)
            _audit(request.user, 'edit', 'User', user.pk, old_value, new_value)
            if old_role != new_role:
                _audit(request.user, 'role_change', 'User', user.pk, old_value, new_value)
        return redirect('ict_staff')
    return render(request, 'portal/ict/staff_form.html', {
        'form': form,
        'heading': 'Edit staff account',
        'staff_user': user,
    })


@role_required(get_user_model().Role.ICT)
@require_POST
def ict_staff_deactivate(request, user_id):
    User = get_user_model()
    user = get_object_or_404(_staff_queryset(), pk=user_id)
    if user.pk == request.user.pk:
        return HttpResponseForbidden('You cannot deactivate your own account.')

    with transaction.atomic():
        user = get_object_or_404(
            User.objects.select_for_update(),
            pk=user.pk,
            role__in=[role for role, _label in User.Role.choices
                      if role != User.Role.STUDENT],
        )
        if not user.is_active:
            messages.error(request, 'This account is already inactive.')
            return redirect('ict_staff')
        if (
            user.role == User.Role.ICT
            and User.objects.filter(role=User.Role.ICT, is_active=True).count() <= 1
        ):
            return HttpResponseForbidden('The last active ICT user cannot be deactivated.')

        old_value = _staff_values(user)
        user.is_active = False
        user.save(update_fields=['is_active'])
        _audit(request.user, 'deactivate', 'User', user.pk, old_value, _staff_values(user))
    return redirect('ict_staff')


@role_required(get_user_model().Role.ICT)
@require_POST
def ict_staff_reactivate(request, user_id):
    user = get_object_or_404(_staff_queryset(), pk=user_id)
    if user.is_active:
        messages.error(request, 'This account is already active.')
        return redirect('ict_staff')

    with transaction.atomic():
        old_value = _staff_values(user)
        user.is_active = True
        user.save(update_fields=['is_active'])
        _audit(request.user, 'reactivate', 'User', user.pk, old_value, _staff_values(user))
    return redirect('ict_staff')


@role_required(get_user_model().Role.ICT)
@require_http_methods(['GET', 'POST'])
def ict_staff_reset_password(request, user_id):
    user = get_object_or_404(_staff_queryset(), pk=user_id)
    form = TemporaryPasswordForm(request.POST or None, user=user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            old_value = f'must_change_password={user.must_change_password}'
            user.set_password(form.cleaned_data['password1'])
            user.must_change_password = True
            user.save(update_fields=['password', 'must_change_password'])
            _audit(
                request.user,
                'password_reset',
                'User',
                user.pk,
                old_value,
                'temporary_password_set=True; must_change_password=True',
            )
        return redirect('ict_staff')
    return render(request, 'portal/ict/password_reset.html', {
        'form': form,
        'staff_user': user,
    })
