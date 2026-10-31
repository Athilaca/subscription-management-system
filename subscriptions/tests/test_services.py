"""State machine guards, numbering, line snapshots, renewal and templates."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from catalog.models import Plan, Product, ProductVariant, TaxRule
from subscriptions import services
from subscriptions.models import (
    LineVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
)

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate


@pytest.fixture
def customer(customer_user):
    return customer_user


@pytest.fixture
def staff(staff_user):
    return staff_user


@pytest.fixture
def plan(db):
    return Plan.objects.create(
        name="Standard monthly",
        price=Decimal("99.00"),
        billing_period=Plan.BillingPeriods.MONTHLY,
    )


@pytest.fixture
def product(db):
    return Product.objects.create(
        name="ERP Suite", sales_price=Decimal("100.00"), cost_price=Decimal("40.00")
    )


@pytest.fixture
def odoo_variant(product):
    return ProductVariant.objects.create(
        product=product, name="Odoo", price_adjustment=Decimal("560.00")
    )


def make_subscription(customer, plan, status=Subscription.Status.DRAFT, **kwargs):
    defaults = dict(
        customer=customer,
        plan=plan,
        start_date=TODAY(),
        quantity=1,
    )
    defaults.update(kwargs)
    sub = Subscription.objects.create(**defaults)
    if status != Subscription.Status.DRAFT:
        sub.status = status
        sub.save()
    return sub


# --- numbering -----------------------------------------------------------------------

def test_subscription_numbers_are_sequential(customer, plan):
    sub1 = make_subscription(customer, plan)
    sub2 = make_subscription(customer, plan)
    assert sub1.number == "SUB-000001"
    assert sub2.number == "SUB-000002"


# --- state machine -------------------------------------------------------------------

def test_happy_path_walks_all_statuses(customer, plan):
    sub = make_subscription(customer, plan)
    for target in (
        Subscription.Status.QUOTATION,
        Subscription.Status.CONFIRMED,
        Subscription.Status.ACTIVE,
    ):
        services.transition(sub, target)
    assert sub.status == Subscription.Status.ACTIVE
    assert sub.next_billing_date == TODAY()


def test_activation_with_future_start_bills_from_start_date(customer, plan):
    future = TODAY() + timedelta(days=10)
    sub = make_subscription(customer, plan, status=Subscription.Status.CONFIRMED,
                            start_date=future)
    services.transition(sub, Subscription.Status.ACTIVE)
    assert sub.next_billing_date == future


def test_illegal_transition_raises(customer, plan):
    sub = make_subscription(customer, plan)
    with pytest.raises(services.InvalidTransition):
        services.transition(sub, Subscription.Status.ACTIVE)  # draft → active
    with pytest.raises(services.InvalidTransition):
        services.transition(sub, Subscription.Status.CLOSED)  # draft → closed


def test_closed_is_terminal(customer, plan):
    sub = make_subscription(
        customer, plan, status=Subscription.Status.ACTIVE,
        start_date=TODAY() - timedelta(days=30),
        expiry_date=TODAY() - timedelta(days=1),
    )
    services.transition(sub, Subscription.Status.CLOSED)
    with pytest.raises(services.InvalidTransition):
        services.transition(sub, Subscription.Status.ACTIVE)


def test_pause_blocked_without_plan_flag(customer, plan):
    plan.allow_pause = False
    plan.save()
    sub = make_subscription(customer, plan, status=Subscription.Status.ACTIVE)
    with pytest.raises(services.InvalidTransition):
        services.transition(sub, Subscription.Status.PAUSED)


def test_pause_sets_and_resume_restores_billing(customer, plan):
    sub = make_subscription(customer, plan, status=Subscription.Status.ACTIVE)
    services.transition(sub, Subscription.Status.PAUSED)
    assert sub.next_billing_date is None
    services.resume(sub)
    assert sub.status == Subscription.Status.ACTIVE
    assert sub.next_billing_date == TODAY()


def test_early_close_blocked_without_plan_flag(customer, plan):
    plan.allow_close_early = False
    plan.save()
    sub = make_subscription(
        customer, plan, status=Subscription.Status.ACTIVE,
        expiry_date=TODAY() + timedelta(days=30),
    )
    with pytest.raises(services.InvalidTransition):
        services.transition(sub, Subscription.Status.CLOSED)


def test_close_at_expiry_allowed_even_without_flag(customer, plan):
    plan.allow_close_early = False
    plan.save()
    sub = make_subscription(
        customer, plan, status=Subscription.Status.ACTIVE,
        start_date=TODAY() - timedelta(days=30),
        expiry_date=TODAY() - timedelta(days=1),
    )
    services.transition(sub, Subscription.Status.CLOSED)
    assert sub.status == Subscription.Status.CLOSED


def test_confirmation_requires_plan_availability(customer, plan):
    plan.available_from = TODAY() + timedelta(days=5)
    plan.available_until = TODAY() + timedelta(days=30)
    plan.save()
    sub = make_subscription(customer, plan, status=Subscription.Status.QUOTATION)
    with pytest.raises(services.InvalidTransition):
        services.transition(sub, Subscription.Status.CONFIRMED)


# --- renewal -------------------------------------------------------------------------

def make_line(sub, product, variant=None):
    line = SubscriptionLine.objects.create(subscription=sub, product=product, quantity=2)
    if variant:
        LineVariant.objects.create(line=line, variant=variant,
                                   price_adjustment=variant.price_adjustment)
    return line


def test_renewal_copies_lines_and_starts_after_expiry(customer, plan, product, odoo_variant):
    sub = make_subscription(
        customer, plan, status=Subscription.Status.ACTIVE,
        expiry_date=TODAY(),
    )
    line = make_line(sub, product, odoo_variant)
    services.transition(sub, Subscription.Status.CLOSED)

    renewal = services.create_renewal(sub)
    assert renewal.status == Subscription.Status.DRAFT
    assert renewal.number != sub.number
    assert renewal.start_date == TODAY() + timedelta(days=1)
    assert renewal.lines.count() == 1
    new_line = renewal.lines.get()
    assert new_line.product == product
    assert new_line.variant_selections.get().variant == odoo_variant


def test_renewal_blocked_while_active(customer, plan):
    sub = make_subscription(customer, plan, status=Subscription.Status.ACTIVE)
    with pytest.raises(services.InvalidTransition):
        services.create_renewal(sub)


def test_renewal_blocked_without_plan_flag(customer, plan):
    plan.allow_renewal = False
    plan.save()
    sub = make_subscription(
        customer, plan, status=Subscription.Status.ACTIVE,
        start_date=TODAY() - timedelta(days=30),
        expiry_date=TODAY() - timedelta(days=1),
    )
    services.transition(sub, Subscription.Status.CLOSED)
    with pytest.raises(services.InvalidTransition):
        services.create_renewal(sub)


# --- period advancement ---------------------------------------------------------------

def test_advance_period_handles_month_end():
    assert services.advance_period(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert services.advance_period(date(2026, 10, 31), "monthly") == date(2026, 11, 30)
    assert services.advance_period(date(2026, 11, 1), "daily") == date(2026, 11, 2)
    assert services.advance_period(date(2026, 11, 1), "weekly") == date(2026, 11, 8)
    assert services.advance_period(date(2026, 2, 28), "yearly") == date(2027, 2, 28)


# --- line snapshots -------------------------------------------------------------------

def test_recalculate_snapshots_price_and_tax(customer, plan, product, odoo_variant):
    TaxRule.objects.create(name="VAT", rate=Decimal("0.15"))
    sub = make_subscription(customer, plan)
    line = SubscriptionLine.objects.create(subscription=sub, product=product, quantity=2)
    LineVariant.objects.create(line=line, variant=odoo_variant,
                               price_adjustment=Decimal("560.00"))

    services.recalculate_subscription(sub)
    line.refresh_from_db()
    assert line.unit_price == Decimal("660.00")       # 100 + 560
    assert line.tax_rate == Decimal("0.15")
    assert line.amount == Decimal("1320.00")


def test_recalculate_survives_later_catalog_price_change(customer, plan, product):
    sub = make_subscription(customer, plan)
    SubscriptionLine.objects.create(subscription=sub, product=product, quantity=1)
    services.recalculate_subscription(sub)
    product.sales_price = Decimal("999.00")
    product.save()
    line = sub.lines.get()
    assert line.unit_price == Decimal("100.00")  # snapshot stays


# --- quotation templates ---------------------------------------------------------------

def test_start_from_template_copies_plan_lines_and_validity(
    customer, staff, plan, product
):
    TaxRule.objects.create(name="VAT", rate=Decimal("0.15"))
    template = QuotationTemplate.objects.create(
        name="ERP offer", plan=plan, validity_days=14, created_by=staff
    )
    QuotationTemplateLine.objects.create(template=template, product=product, quantity=3)

    sub = services.start_from_template(template, customer, owner=staff)
    assert sub.status == Subscription.Status.DRAFT
    assert sub.plan == plan
    assert sub.valid_until == TODAY() + timedelta(days=14)
    assert sub.owner == staff
    assert sub.lines.count() == 1
    line = sub.lines.get()
    assert line.quantity == 3
    assert line.unit_price == Decimal("100.00")  # recalculated from catalog


def test_start_from_template_requires_plan(customer, staff, product):
    template = QuotationTemplate.objects.create(name="Bare offer", validity_days=30)
    QuotationTemplateLine.objects.create(template=template, product=product, quantity=1)
    with pytest.raises(ValueError):
        services.start_from_template(template, customer)
