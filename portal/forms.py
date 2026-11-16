import re

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from .models import Program


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
