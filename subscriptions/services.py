"""Subscription state machine and lifecycle services.

The TRANSITIONS map is the single source of truth: views render transition
buttons from it (so the UI can never offer an illegal action) and the
``transition`` service enforces it (so the API can never accept one).
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.services import compute_unit_price, effective_tax_rate
from subscriptions.models import (
    LineVariant,
    QuotationTemplate,
    Subscription,
    SubscriptionLine,
)

TWO_PLACES = Decimal("0.01")


class InvalidTransition(ValidationError):
    """Raised when a status change is illegal for the subscription's current
    state or violates the plan's behaviour flags."""


# Maps current status -> set of legal next statuses.
TRANSITIONS: dict[str, set[str]] = {
    Subscription.Status.DRAFT: {Subscription.Status.QUOTATION},
    Subscription.Status.QUOTATION: {Subscription.Status.CONFIRMED, Subscription.Status.DRAFT},
    Subscription.Status.CONFIRMED: {Subscription.Status.ACTIVE, Subscription.Status.QUOTATION},
    Subscription.Status.ACTIVE: {Subscription.Status.PAUSED, Subscription.Status.CLOSED},
    Subscription.Status.PAUSED: {Subscription.Status.ACTIVE, Subscription.Status.CLOSED},
    Subscription.Status.CLOSED: set(),  # renewal creates a NEW subscription
}


@dataclass(frozen=True)
class TransitionRule:
    target: str
    label: str
    requires_flag: str | None = None  # plan flag that must be true, if any


# Ordered, human-readable list used by templates to render allowed actions.
ACTION_BUTTONS: dict[str, tuple[TransitionRule, ...]] = {
    Subscription.Status.DRAFT: (
        TransitionRule(Subscription.Status.QUOTATION, "Send quotation"),
    ),
    Subscription.Status.QUOTATION: (
        TransitionRule(Subscription.Status.CONFIRMED, "Confirm"),
        TransitionRule(Subscription.Status.DRAFT, "Back to draft"),
    ),
    Subscription.Status.CONFIRMED: (
        TransitionRule(Subscription.Status.ACTIVE, "Activate"),
        TransitionRule(Subscription.Status.QUOTATION, "Back to quotation"),
    ),
    Subscription.Status.ACTIVE: (
        TransitionRule(Subscription.Status.PAUSED, "Pause", requires_flag="allow_pause"),
        TransitionRule(Subscription.Status.CLOSED, "Close", requires_flag="allow_close_early"),
    ),
    Subscription.Status.PAUSED: (
        TransitionRule(Subscription.Status.ACTIVE, "Resume"),
        TransitionRule(Subscription.Status.CLOSED, "Close", requires_flag="allow_close_early"),
    ),
    Subscription.Status.CLOSED: (),
}


def allowed_actions(sub: Subscription) -> list[TransitionRule]:
    """Actions legal for this subscription right now, with plan-flag filtering
    applied — exactly what the detail template should render as buttons."""
    today = timezone.localdate()
    actions = []
    for rule in ACTION_BUTTONS.get(sub.status, ()):
        if rule.requires_flag and not getattr(sub.plan, rule.requires_flag):
            continue
        if rule.target == Subscription.Status.CLOSED and sub.status == (
            Subscription.Status.PAUSED
        ) and sub.expiry_date and sub.expiry_date <= today:
            actions.append(TransitionRule(rule.target, rule.label))  # past expiry: always allowed
            continue
        actions.append(rule)
    return actions


def transition(sub: Subscription, new_status: str) -> Subscription:
    """Apply a guarded status change. Raises InvalidTransition when the move is
    illegal. Activation starts the billing clock; pausing stops it."""
    legal = TRANSITIONS[sub.status]
    if new_status not in legal:
        raise InvalidTransition(
            f"Cannot move subscription from “{sub.get_status_display()}” "
            f"to “{new_status}”."
        )
    today = timezone.localdate()

    if new_status == Subscription.Status.PAUSED and not sub.plan.allow_pause:
        raise InvalidTransition("This plan does not allow pausing.")

    if new_status == Subscription.Status.CLOSED:
        past_expiry = sub.expiry_date is not None and sub.expiry_date <= today
        if not past_expiry and not sub.plan.allow_close_early:
            raise InvalidTransition("This plan does not allow closing early.")

    if new_status == Subscription.Status.CONFIRMED and not sub.plan.is_available_on(today):
        raise InvalidTransition("The plan is not currently available.")

    sub.status = new_status
    if new_status == Subscription.Status.ACTIVE:
        # Activation: billing starts on the start date, but never retroactively
        # before today. Resume-from-pause also lands here: billing restarts today.
        sub.next_billing_date = max(sub.start_date, today)
    elif new_status == Subscription.Status.PAUSED:
        sub.next_billing_date = None

    sub.full_clean(exclude={"number"})
    sub.save()
    return sub


def resume(sub: Subscription) -> Subscription:
    """Resume a paused subscription: billing restarts today."""
    if sub.status != Subscription.Status.PAUSED:
        raise InvalidTransition("Only paused subscriptions can be resumed.")
    sub.status = Subscription.Status.ACTIVE
    sub.next_billing_date = timezone.localdate()
    sub.full_clean(exclude={"number"})
    sub.save()
    return sub


def advance_period(day, billing_period: str):
    """Next billing date for a cycle; relativedelta maps month ends correctly
    (Jan 31 + 1 month = Feb 28)."""
    deltas = {
        "daily": relativedelta(days=1),
        "weekly": relativedelta(weeks=1),
        "monthly": relativedelta(months=1),
        "yearly": relativedelta(years=1),
    }
    return day + deltas[billing_period]


def create_renewal(sub: Subscription) -> Subscription:
    """Renewal: a NEW subscription starting the day after the old one expires,
    with copied lines. The old subscription stays Closed."""
    if sub.status != Subscription.Status.CLOSED:
        raise InvalidTransition("Only closed subscriptions can be renewed.")
    if not sub.plan.allow_renewal:
        raise InvalidTransition("This plan does not allow renewal.")
    if sub.expiry_date is None:
        raise InvalidTransition("Cannot renew a subscription without an expiry date.")

    start = sub.expiry_date + relativedelta(days=1)
    with transaction.atomic():
        renewal = Subscription.objects.create(
            customer=sub.customer,
            plan=sub.plan,
            quantity=sub.quantity,
            start_date=start,
            expiry_date=advance_period(start, sub.plan.billing_period),
            payment_terms_days=sub.payment_terms_days,
            status=Subscription.Status.DRAFT,
            owner=sub.owner,
            notes=f"Renewal of {sub.number}. {sub.notes}".strip(),
        )
        for line in sub.lines.all():
            new_line = SubscriptionLine.objects.create(
                subscription=renewal,
                product=line.product,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=line.tax_rate,
                amount=line.amount,
                sort_order=line.sort_order,
            )
            for selection in line.variant_selections.select_related("variant"):
                LineVariant.objects.create(
                    line=new_line,
                    variant=selection.variant,
                    price_adjustment=selection.price_adjustment,
                )
    return renewal


def recalculate_subscription(sub: Subscription) -> None:
    """Re-snapshot every line's unit price (product + chosen variant
    adjustments) and tax rate from the catalog, then store amounts."""
    for line in sub.lines.select_related("product").prefetch_related(
        "variant_selections__variant"
    ):
        variants = [sel.variant for sel in line.variant_selections.all()]
        line.unit_price = compute_unit_price(line.product, variants)
        line.tax_rate = effective_tax_rate(line.product)
        line.amount = (line.unit_price * line.quantity).quantize(TWO_PLACES, ROUND_HALF_UP)
        line.save(update_fields=["unit_price", "tax_rate", "amount"])
        for selection in line.variant_selections.all():
            if selection.price_adjustment != selection.variant.price_adjustment:
                selection.price_adjustment = selection.variant.price_adjustment
                selection.save(update_fields=["price_adjustment"])


def start_from_template(template: QuotationTemplate, customer, owner=None, start_date=None) -> Subscription:
    """Create a DRAFT subscription from a quotation template: copies the plan,
    product lines, and sets quotation validity from the template."""
    from django.utils import timezone

    if template.plan_id is None:
        raise ValueError("Template must have a plan to start a subscription from.")
    start_date = start_date or timezone.localdate()
    with transaction.atomic():
        sub = Subscription.objects.create(
            customer=customer,
            plan=template.plan,
            start_date=start_date,
            status=Subscription.Status.DRAFT,
            owner=owner,
            valid_until=start_date + relativedelta(days=template.validity_days),
            notes=f"Created from template “{template.name}”.",
        )
        SubscriptionLine.objects.bulk_create([
            SubscriptionLine(
                subscription=sub,
                product=line.product,
                quantity=line.quantity,
                sort_order=line.sort_order,
            )
            for line in template.lines.select_related("product")
        ])
        recalculate_subscription(sub)
    return sub
