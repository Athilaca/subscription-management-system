import pytest

from accounts.models import User

VALID_PASSWORD = "Bright!Loop42"


def make_user(email, role, password=VALID_PASSWORD):
    return User.objects.create_user(
        email=email, password=password, role=role, first_name="Test"
    )


@pytest.fixture
def admin_user(db):
    return make_user("admin@example.com", User.Roles.ADMIN)


@pytest.fixture
def staff_user(db):
    return make_user("staff@example.com", User.Roles.STAFF)


@pytest.fixture
def customer_user(db):
    return make_user("customer@example.com", User.Roles.CUSTOMER)


@pytest.fixture
def client_logged_admin(admin_user, client):
    client.force_login(admin_user)
    return client


@pytest.fixture
def client_logged_staff(staff_user, client):
    client.force_login(staff_user)
    return client


@pytest.fixture
def client_logged_customer(customer_user, client):
    client.force_login(customer_user)
    return client
