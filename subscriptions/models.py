from django.conf import settings
from django.db import models
from django.db.models import Q

from core.services import allocate_number


class Subscription(models.Model):
    """A customer's subscription: its own number, plan, dates, payment terms and
    priced lines. Moves Draft → Quotation → Confirmed → Active → Closed
    (with Paused in between Active and Closed) — see services.TRANSITIONS."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUOTATION = "quotation", "Quotation"
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        limit_choices_to={"role": "customer"},
    )
    plan = models.ForeignKey(
        "catalog.Plan", on_delete=models.PROTECT, related_name="subscriptions"
    )
    quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    payment_terms_days = models.PositiveSmallIntegerField(
        default=0, help_text="0 = due on receipt; otherwise net days"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    valid_until = models.DateField(
        null=True, blank=True, help_text="Quotation validity (set from the template)"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_subscriptions",
        limit_choices_to={"role__in": ["admin", "staff"]},
        help_text="Sales rep",
    )
    notes = models.TextField(blank=True)
    next_billing_date = models.DateField(
        null=True,
        blank=True,
        help_text="Next cycle to bill; null = not active or paused",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "next_billing_date"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["expiry_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(expiry_date__isnull=True)
                | Q(expiry_date__gte=models.F("start_date")),
                name="subscription_expiry_not_before_start",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="subscription_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.number} — {self.customer.email}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = allocate_number("subscription", "SUB-")
        super().save(*args, **kwargs)


class SubscriptionLine(models.Model):
    """A priced line snapshotting the product, chosen variants, unit price and
    tax rate at the time it was added — catalog changes never rewrite history."""

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="subscription_lines"
    )
    quantity = models.PositiveIntegerField(default=1)
    variants = models.ManyToManyField(
        "catalog.ProductVariant", through="LineVariant", related_name="subscription_lines"
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "pk")

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity}"


class LineVariant(models.Model):
    """A variant chosen on a subscription line, with its price adjustment
    snapshotted so later catalog edits don't change agreed prices."""

    line = models.ForeignKey(
        SubscriptionLine, on_delete=models.CASCADE, related_name="variant_selections"
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="line_selections"
    )
    price_adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["line", "variant"], name="line_variant_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.line} — {self.variant.name}"


class QuotationTemplate(models.Model):
    """A starting point for offers: the right plan and product lines, valid for
    a set number of days."""

    name = models.CharField(max_length=200, unique=True)
    plan = models.ForeignKey(
        "catalog.Plan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quotation_templates",
    )
    validity_days = models.PositiveIntegerField(default=30)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(
        QuotationTemplate, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="quotation_template_lines"
    )
    quantity = models.PositiveIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "pk")

    def __str__(self) -> str:
        return f"{self.template.name} — {self.product.name} × {self.quantity}"
