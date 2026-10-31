"""Model constraints and plan availability."""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from catalog.models import Plan, Product, ProductVariant

pytestmark = pytest.mark.django_db


@pytest.fixture
def product(db):
    return Product.objects.create(
        name="ERP Suite",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("40.00"),
    )


def test_variant_name_unique_per_product(product):
    ProductVariant.objects.create(product=product, name="Odoo", price_adjustment=Decimal("560"))
    with pytest.raises(IntegrityError):
        ProductVariant.objects.create(product=product, name="Odoo")


def test_variant_name_reusable_across_products(product):
    other = Product.objects.create(
        name="CRM", sales_price=Decimal("80"), cost_price=Decimal("30")
    )
    ProductVariant.objects.create(product=product, name="Odoo")
    variant = ProductVariant.objects.create(product=other, name="Odoo")  # fine
    assert variant.pk is not None


def test_product_prices_must_be_non_negative(db):
    with pytest.raises(IntegrityError):
        Product.objects.create(name="Bad", sales_price=Decimal("-1"), cost_price=Decimal("1"))


def test_plan_price_must_be_non_negative(db):
    with pytest.raises(IntegrityError):
        Plan.objects.create(name="Bad plan", price=Decimal("-5"),
                            billing_period=Plan.BillingPeriods.MONTHLY)


def test_plan_availability_window_must_be_ordered(db):
    with pytest.raises(IntegrityError):
        Plan.objects.create(
            name="Backwards plan",
            price=Decimal("10"),
            billing_period=Plan.BillingPeriods.DAILY,
            available_from=date(2026, 12, 31),
            available_until=date(2026, 1, 1),
        )


def make_plan(**kwargs):
    defaults = dict(
        name="Standard monthly",
        price=Decimal("99.00"),
        billing_period=Plan.BillingPeriods.MONTHLY,
    )
    defaults.update(kwargs)
    return Plan.objects.create(**defaults)


def test_plan_availability_open_ended():
    plan = make_plan()
    assert plan.is_available_on(date(2026, 1, 1))
    assert plan.is_available_on(date(2030, 12, 31))


def test_plan_availability_window_respected():
    plan = make_plan(available_from=date(2026, 1, 1), available_until=date(2026, 6, 30))
    assert plan.is_available_on(date(2026, 3, 15))
    assert not plan.is_available_on(date(2025, 12, 31))
    assert not plan.is_available_on(date(2026, 7, 1))


def test_inactive_plan_unavailable():
    plan = make_plan(is_active=False)
    assert not plan.is_available_on(date(2026, 10, 31))
