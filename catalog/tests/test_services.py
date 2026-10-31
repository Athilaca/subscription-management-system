"""Pricing and tax services — the math the whole billing chain depends on."""
from decimal import Decimal

import pytest

from catalog.models import Product, ProductVariant, TaxRule
from catalog.services import compute_unit_price, effective_tax_rate, line_tax

pytestmark = pytest.mark.django_db


@pytest.fixture
def product(db):
    return Product.objects.create(
        name="ERP Suite",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("40.00"),
    )


@pytest.fixture
def odoo_variant(product):
    return ProductVariant.objects.create(
        product=product, name="Odoo", price_adjustment=Decimal("560.00")
    )


@pytest.fixture
def discount_variant(product):
    return ProductVariant.objects.create(
        product=product, name="Standard", price_adjustment=Decimal("-10.00")
    )


def test_unit_price_without_variants(product):
    assert compute_unit_price(product) == Decimal("100.00")


def test_unit_price_with_positive_variant(product, odoo_variant):
    # The brief's exact case: choosing the Odoo brand adds 560 to the price
    assert compute_unit_price(product, [odoo_variant]) == Decimal("660.00")


def test_unit_price_with_negative_variant(product, discount_variant):
    assert compute_unit_price(product, [discount_variant]) == Decimal("90.00")


def test_unit_price_sums_multiple_variants(product, odoo_variant, discount_variant):
    assert compute_unit_price(product, [odoo_variant, discount_variant]) == Decimal("650.00")


def test_line_tax_rounds_half_up():
    assert line_tax(Decimal("33.33"), Decimal("3"), Decimal("0.15")) == Decimal("15.00")
    assert line_tax(Decimal("10.00"), Decimal("1"), Decimal("0.155")) == Decimal("1.55")


def test_no_tax_rule_means_zero_tax(product):
    assert effective_tax_rate(product) == Decimal("0")


def test_global_tax_rule_applies(product):
    TaxRule.objects.create(name="VAT", rate=Decimal("0.15"))
    assert effective_tax_rate(product) == Decimal("0.15")


def test_product_specific_rule_beats_global(product):
    TaxRule.objects.create(name="VAT", rate=Decimal("0.15"))
    TaxRule.objects.create(
        name="Luxury rate", rate=Decimal("0.20"), applies_to=product
    )
    assert effective_tax_rate(product) == Decimal("0.20")


def test_priority_beats_specificity(product):
    other = Product.objects.create(
        name="Other", sales_price=Decimal("50.00"), cost_price=Decimal("10.00")
    )
    TaxRule.objects.create(name="Low priority specific", rate=Decimal("0.30"),
                           applies_to=product, priority=1)
    TaxRule.objects.create(name="High priority global", rate=Decimal("0.10"),
                           priority=5)
    assert effective_tax_rate(product) == Decimal("0.10")
    assert effective_tax_rate(other) == Decimal("0.10")


def test_inactive_rule_ignored(product):
    TaxRule.objects.create(name="Retired", rate=Decimal("0.30"), is_active=False)
    assert effective_tax_rate(product) == Decimal("0")


def test_higher_rate_breaks_priority_tie(product):
    TaxRule.objects.create(name="A", rate=Decimal("0.15"), priority=3)
    TaxRule.objects.create(name="B", rate=Decimal("0.20"), priority=3)
    assert effective_tax_rate(product) == Decimal("0.20")
