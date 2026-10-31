"""Catalog pricing and tax services — the single source of truth for unit price
and effective tax rate computation. Snapshotted onto subscription/invoice lines."""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

from catalog.models import TaxRule

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def compute_unit_price(product, variants=()) -> Decimal:
    """Sales price plus the sum of the selected variants' adjustments.

    E.g. product at 100 with the 'Odoo' brand variant (+560) prices at 660.
    """
    adjustments = sum((v.price_adjustment for v in variants), Decimal("0"))
    return (product.sales_price + adjustments).quantize(TWO_PLACES, ROUND_HALF_UP)


def effective_tax_rate(product, today=None) -> Decimal:
    """Highest-priority active rule matching the product (specific beats global);
    falls back to 0 when no rule applies."""
    rules = TaxRule.objects.filter(is_active=True).filter(
        Q(applies_to__isnull=True) | Q(applies_to=product)
    )
    best = max(rules, key=lambda r: (r.priority, r.rate), default=None)
    return best.rate if best else Decimal("0")


def line_tax(unit_price: Decimal, quantity: Decimal, rate: Decimal) -> Decimal:
    """Tax amount for a line, rounded half-up to 2 places."""
    return (unit_price * quantity * rate).quantize(TWO_PLACES, ROUND_HALF_UP)
