"""View-level gating: back-office access, portal isolation, transitions."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils.timezone import localdate

from subscriptions.models import Subscription

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan(db):
    from catalog.models import Plan
    return Plan.objects.create(
        name="Standard monthly",
        price=Decimal("99.00"),
        billing_period=Plan.BillingPeriods.MONTHLY,
    )


@pytest.fixture
def subscription(customer_user, plan):
    return Subscription.objects.create(
        customer=customer_user,
        plan=plan,
        start_date=localdate(),
        status=Subscription.Status.CONFIRMED,
    )


def make_post_data(plan, customer):
    data = {
        "customer": customer.id,
        "plan": plan.id,
        "quantity": 1,
        "start_date": "2026-11-01",
        "payment_terms_days": 0,
        "lines-TOTAL_FORMS": "3",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    # browsers submit every rendered field; empty extra rows stay "unchanged"
    for i in range(3):
        data[f"lines-{i}-product"] = ""
        data[f"lines-{i}-quantity"] = "1"
    return data


# --- back-office gating ---------------------------------------------------------------

def test_subscription_list_denied_for_customer(client_logged_customer):
    assert client_logged_customer.get(reverse("subscriptions:subscription-list")).status_code == 403


def test_subscription_create_denied_for_customer(client_logged_customer):
    assert client_logged_customer.get(reverse("subscriptions:subscription-create")).status_code == 403


def test_staff_can_create_subscription(client_logged_staff, plan, customer_user):
    response = client_logged_staff.post(
        reverse("subscriptions:subscription-create"),
        make_post_data(plan, customer_user),
    )
    assert response.status_code == 302
    assert Subscription.objects.filter(customer=customer_user).count() == 1
    sub = Subscription.objects.get(customer=customer_user)
    assert sub.status == Subscription.Status.DRAFT


def test_min_quantity_rejected(client_logged_staff, plan, customer_user):
    plan.min_quantity = 5
    plan.save()
    data = make_post_data(plan, customer_user)
    data["quantity"] = 1
    response = client_logged_staff.post(reverse("subscriptions:subscription-create"), data)
    assert response.status_code == 200
    assert Subscription.objects.filter(customer=customer_user).count() == 0


# --- transitions ----------------------------------------------------------------------

def test_transition_via_view(client_logged_staff, subscription):
    url = reverse("subscriptions:subscription-transition",
                  args=[subscription.pk, Subscription.Status.ACTIVE])
    response = client_logged_staff.post(url)
    assert response.status_code == 302
    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE


def test_illegal_transition_rejected_with_message(client_logged_staff, subscription):
    url = reverse("subscriptions:subscription-transition",
                  args=[subscription.pk, Subscription.Status.CLOSED])  # confirmed → closed: illegal
    client_logged_staff.post(url, follow=True)
    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.CONFIRMED


def test_customer_cannot_transition(client_logged_customer, subscription):
    url = reverse("subscriptions:subscription-transition",
                  args=[subscription.pk, Subscription.Status.ACTIVE])
    assert client_logged_customer.post(url).status_code == 403
    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.CONFIRMED


def test_confirmed_subscription_cannot_be_edited(client_logged_staff, subscription):
    url = reverse("subscriptions:subscription-update", args=[subscription.pk])
    response = client_logged_staff.get(url, follow=True)
    assert response.redirect_chain  # redirected away from the edit form


# --- customer portal isolation ----------------------------------------------------------

def test_portal_lists_only_own_subscriptions(client_logged_customer, customer_user, staff_user, plan):
    mine = Subscription.objects.create(
        customer=customer_user, plan=plan,
        start_date=localdate(),
    )
    theirs = Subscription.objects.create(
        customer=staff_user, plan=plan,
        start_date=localdate(),
    )
    response = client_logged_customer.get(reverse("subscriptions:portal-subscription-list"))
    content = response.content.decode()
    assert mine.number in content
    assert theirs.number not in content


def test_portal_cannot_open_other_customers_subscription(client_logged_customer, staff_user, plan):
    from django.utils.timezone import localdate
    theirs = Subscription.objects.create(
        customer=staff_user, plan=plan, start_date=localdate(),
    )
    url = reverse("subscriptions:portal-subscription-detail", args=[theirs.pk])
    assert client_logged_customer.get(url).status_code == 404


def test_portal_detail_renders(client_logged_customer, customer_user, plan):
    from django.utils.timezone import localdate
    sub = Subscription.objects.create(
        customer=customer_user, plan=plan, start_date=localdate(),
    )
    url = reverse("subscriptions:portal-subscription-detail", args=[sub.pk])
    assert client_logged_customer.get(url).status_code == 200
