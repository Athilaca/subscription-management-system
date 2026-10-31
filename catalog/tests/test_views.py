"""Role gating and the product + variant create flow."""
from decimal import Decimal

import pytest
from django.urls import reverse

from catalog.models import Plan, Product, TaxRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def product(db):
    return Product.objects.create(
        name="ERP Suite",
        product_type=Product.Types.SUBSCRIPTION,
        sales_price=Decimal("100.00"),
        cost_price=Decimal("40.00"),
    )


@pytest.fixture
def plan(db):
    return Plan.objects.create(
        name="Standard monthly",
        price=Decimal("99.00"),
        billing_period=Plan.BillingPeriods.MONTHLY,
    )


@pytest.fixture
def tax_rule(db):
    return TaxRule.objects.create(name="VAT", rate=Decimal("0.15"))


# --- lists: staff and admin may browse; customers may not ---------------------------

LIST_URLS = ("catalog:product-list", "catalog:plan-list", "catalog:taxrule-list")


@pytest.mark.parametrize("url_name", LIST_URLS)
def test_catalog_lists_denied_for_customer(client_logged_customer, url_name):
    assert client_logged_customer.get(reverse(url_name)).status_code == 403


@pytest.mark.parametrize("url_name", LIST_URLS)
def test_catalog_lists_visible_to_staff(client_logged_staff, url_name):
    assert client_logged_staff.get(reverse(url_name)).status_code == 200


@pytest.mark.parametrize("url_name", LIST_URLS)
def test_catalog_lists_visible_to_admin(client_logged_admin, url_name):
    assert client_logged_admin.get(reverse(url_name)).status_code == 200


# --- editing: admin only -------------------------------------------------------------

def test_staff_cannot_edit_product(client_logged_staff, product):
    url = reverse("catalog:product-update", args=[product.pk])
    assert client_logged_staff.get(url).status_code == 403


def test_staff_cannot_edit_plan(client_logged_staff, plan):
    url = reverse("catalog:plan-update", args=[plan.pk])
    assert client_logged_staff.get(url).status_code == 403


def test_staff_cannot_edit_tax_rule(client_logged_staff, tax_rule):
    url = reverse("catalog:taxrule-update", args=[tax_rule.pk])
    assert client_logged_staff.get(url).status_code == 403


def test_admin_can_edit_plan(client_logged_admin, plan):
    url = reverse("catalog:plan-update", args=[plan.pk])
    assert client_logged_admin.get(url).status_code == 200


def test_staff_cannot_create_product(client_logged_staff):
    assert client_logged_staff.get(reverse("catalog:product-create")).status_code == 403


def test_customer_cannot_create_plan(client_logged_customer):
    assert client_logged_customer.get(reverse("catalog:plan-create")).status_code == 403


# --- product creation with variants (the Odoo +560 case) -----------------------------

def test_admin_creates_product_with_variant(client_logged_admin):
    form_data = {
        "name": "ERP Suite",
        "product_type": Product.Types.SUBSCRIPTION,
        "sales_price": "100.00",
        "cost_price": "40.00",
        "notes": "",
        "is_active": "on",
        # inline formset management
        "variants-TOTAL_FORMS": "2",
        "variants-INITIAL_FORMS": "0",
        "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000",
        "variants-0-name": "Odoo",
        "variants-0-price_adjustment": "560.00",
        "variants-1-name": "",
        "variants-1-price_adjustment": "0.00",
    }
    response = client_logged_admin.post(reverse("catalog:product-create"), form_data)
    assert response.status_code == 302, response.context["form"].errors if hasattr(response, "context") else None
    product = Product.objects.get(name="ERP Suite")
    variant = product.variants.get(name="Odoo")
    assert variant.price_adjustment == Decimal("560.00")
