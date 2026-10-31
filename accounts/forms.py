from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.forms import UsernameField
from django.utils.translation import gettext_lazy as _

from accounts.models import User


class EmailAuthenticationForm(AuthenticationForm):
    """Login form labeled for email authentication (field stays 'username' internally)."""

    username = UsernameField(
        label=_("Email address"),
        widget=forms.TextInput(attrs={"autofocus": True}),
    )


class BaseSignupForm(UserCreationForm):
    """Shared email-based registration; password rules come from AUTH_PASSWORD_VALIDATORS."""

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone")


class SignupForm(BaseSignupForm):
    """Public signup — always creates a CUSTOMER account."""

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.role = User.Roles.CUSTOMER
        if commit:
            user.save()
        return user


class StaffCreateForm(BaseSignupForm):
    """Admin-only staff account creation — always creates a STAFF account."""

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.role = User.Roles.STAFF
        if commit:
            user.save()
        return user
