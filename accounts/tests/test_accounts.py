"""Signup, roles, staff management gating, and the password-reset email flow."""
import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import User
from conftest import VALID_PASSWORD

pytestmark = pytest.mark.django_db


def test_signup_creates_customer_only(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "joiner@example.com",
            "first_name": "Jo",
            "last_name": "Iner",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        },
    )
    assert response.status_code == 302
    user = User.objects.get(email="joiner@example.com")
    assert user.role == User.Roles.CUSTOMER


def test_duplicate_email_rejected(client, customer_user):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": customer_user.email,
            "first_name": "Du",
            "last_name": "Plicate",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        },
    )
    assert response.status_code == 200
    assert User.objects.filter(email=customer_user.email).count() == 1


def test_login_with_email(client, customer_user):
    response = client.post(
        reverse("accounts:login"),
        {"username": customer_user.email, "password": VALID_PASSWORD},
    )
    assert response.status_code == 302


def test_home_requires_login(client):
    assert client.get(reverse("home")).status_code == 302


# --- staff management is admin-only -------------------------------------------------

STAFF_URLS = ("accounts:staff-list", "accounts:staff-create")


@pytest.mark.parametrize("url_name", STAFF_URLS)
def test_staff_pages_denied_for_customer(client_logged_customer, url_name):
    assert client_logged_customer.get(reverse(url_name)).status_code == 403


@pytest.mark.parametrize("url_name", STAFF_URLS)
def test_staff_pages_denied_for_staff(client_logged_staff, url_name):
    assert client_logged_staff.get(reverse(url_name)).status_code == 403


@pytest.mark.parametrize("url_name", STAFF_URLS)
def test_staff_pages_allowed_for_admin(client_logged_admin, url_name):
    assert client_logged_admin.get(reverse(url_name)).status_code == 200


def test_admin_creates_staff_account(client_logged_admin):
    response = client_logged_admin.post(
        reverse("accounts:staff-create"),
        {
            "email": "newstaff@example.com",
            "first_name": "New",
            "last_name": "Staffer",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        },
    )
    assert response.status_code == 302
    user = User.objects.get(email="newstaff@example.com")
    assert user.role == User.Roles.STAFF
    assert not user.is_superuser


def test_create_superuser_forces_admin_role(db):
    user = User.objects.create_superuser(
        email="root@example.com", password=VALID_PASSWORD
    )
    assert user.role == User.Roles.ADMIN
    assert user.is_staff and user.is_superuser


# --- password reset ------------------------------------------------------------------

def test_password_reset_sends_email(client, customer_user):
    response = client.post(reverse("accounts:password-reset"), {"email": customer_user.email})
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert customer_user.email in mail.outbox[0].to
    assert "reset" in mail.outbox[0].body.lower()
