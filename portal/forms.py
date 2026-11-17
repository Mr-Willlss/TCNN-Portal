import re

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from .models import Program, StudentProfile, _process_passport_photo


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ('name', 'code', 'duration_years')
        widgets = {
            'duration_years': forms.NumberInput(attrs={'min': 1, 'max': 8}),
        }

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if not re.fullmatch(r'[A-Z0-9]+', code):
            raise ValidationError('Use letters and digits only.')
        return code

    def clean_duration_years(self):
        duration = self.cleaned_data['duration_years']
        if not 1 <= duration <= 8:
            raise ValidationError('Duration must be between 1 and 8 years.')
        return duration


def staff_role_choices():
    User = get_user_model()
    return tuple(choice for choice in User.Role.choices if choice[0] != User.Role.STUDENT)


class StaffCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    role = forms.ChoiceField(choices=staff_role_choices)
    password1 = forms.CharField(
        label='Temporary password',
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label='Confirm temporary password',
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise ValidationError('A user with that username already exists.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The two password fields did not match.')
            return cleaned_data

        if password1 and cleaned_data.get('username'):
            User = get_user_model()
            user = User(
                username=cleaned_data['username'],
                first_name=cleaned_data.get('first_name', ''),
                last_name=cleaned_data.get('last_name', ''),
            )
            try:
                password_validation.validate_password(password1, user)
            except ValidationError as error:
                self.add_error('password1', error)
        return cleaned_data


class StaffEditForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    role = forms.ChoiceField(choices=staff_role_choices)


class TemporaryPasswordForm(forms.Form):
    password1 = forms.CharField(
        label='Temporary password',
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label='Confirm temporary password',
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The two password fields did not match.')
            return cleaned_data

        if password1 and self.user:
            try:
                password_validation.validate_password(password1, self.user)
            except ValidationError as error:
                self.add_error('password1', error)
        return cleaned_data


class StudentFormBase(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    matric_number = forms.CharField(max_length=50)
    program = forms.ModelChoiceField(queryset=Program.objects.order_by('name', 'code'))
    year_of_study = forms.IntegerField(min_value=1)
    passport_photo = forms.ImageField(required=False)

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)

    def clean_matric_number(self):
        matric_number = self.cleaned_data['matric_number'].strip().upper()
        profiles = StudentProfile.objects.filter(matric_number__iexact=matric_number)
        if self.profile:
            profiles = profiles.exclude(pk=self.profile.pk)
        User = get_user_model()
        usernames = User.objects.filter(username__iexact=matric_number)
        if self.profile:
            usernames = usernames.exclude(pk=self.profile.user_id)
        if profiles.exists() or usernames.exists():
            raise ValidationError('A student with that matric number already exists.')
        return matric_number

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get('program')
        year_of_study = cleaned_data.get('year_of_study')
        if program and year_of_study and year_of_study > program.duration_years:
            self.add_error(
                'year_of_study',
                f"Year of study cannot exceed this program's duration of {program.duration_years}.",
            )

        upload = cleaned_data.get('passport_photo')
        if upload:
            try:
                _process_passport_photo(upload)
            except ValidationError as error:
                self.add_error('passport_photo', error)
            finally:
                upload.seek(0)
        return cleaned_data


class StudentCreateForm(StudentFormBase):
    temporary_password = forms.CharField(
        label='Temporary password',
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields((
            'first_name',
            'last_name',
            'matric_number',
            'program',
            'year_of_study',
            'temporary_password',
            'passport_photo',
        ))

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('temporary_password')
        matric_number = cleaned_data.get('matric_number')
        if password and matric_number:
            User = get_user_model()
            user = User(
                username=matric_number,
                first_name=cleaned_data.get('first_name', ''),
                last_name=cleaned_data.get('last_name', ''),
                role=User.Role.STUDENT,
            )
            try:
                password_validation.validate_password(password, user)
            except ValidationError as error:
                self.add_error('temporary_password', error)
        return cleaned_data


class StudentEditForm(StudentFormBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields((
            'first_name',
            'last_name',
            'matric_number',
            'program',
            'year_of_study',
            'passport_photo',
        ))


class StudentPasswordResetForm(TemporaryPasswordForm):
    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, user=profile.user if profile else None, **kwargs)
