"""Password policy: >8 chars with uppercase, lowercase and a special character."""
import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.forms import SignupForm

VALID = "Bright!Loop42"


@pytest.mark.parametrize(
    "password",
    [
        "Sh0r!t",               # 6 chars — too short
        "EightC!s",             # 8 chars — must be MORE than eight
        "no_uppercas3!",        # no uppercase
        "NO_LOWERCASE1!",       # no lowercase
        "NoSpecial123x",        # no special character
    ],
)
def test_rejects_weak_passwords(password):
    with pytest.raises(ValidationError):
        validate_password(password)


def test_accepts_compliant_password():
    validate_password(VALID)


@pytest.mark.django_db
def test_signup_form_enforces_policy():
    form = SignupForm(
        data={
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "Customer",
            "password1": "weakpassword",
            "password2": "weakpassword",
        }
    )
    assert not form.is_valid()
    # UserCreationForm runs the password validators on the confirmed password
    assert "password2" in form.errors

    form = SignupForm(
        data={
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "Customer",
            "password1": VALID,
            "password2": VALID,
        }
    )
    assert form.is_valid(), form.errors
