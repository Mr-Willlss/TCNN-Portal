from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError


class InitialICTSetupForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label='Password confirmation',
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        if User._default_manager.filter(username=username).exists():
            raise ValidationError('A user with that username already exists.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The two password fields did not match.')
            return cleaned_data

        if password1 and all(
            cleaned_data.get(field) for field in ('username', 'first_name', 'last_name')
        ):
            User = get_user_model()
            user = User(
                username=cleaned_data['username'],
                first_name=cleaned_data['first_name'],
                last_name=cleaned_data['last_name'],
            )
            try:
                password_validation.validate_password(password1, user)
            except ValidationError as error:
                self.add_error('password1', error)

        return cleaned_data
