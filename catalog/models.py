from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Product(models.Model):
    """A sellable item, offered in variants (e.g. by brand) that adjust the price."""

    class Types(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        SERVICE = "service", "Service"
        GOODS = "goods", "Goods"

    name = models.CharField(max_length=200, unique=True)
    product_type = models.CharField(
        max_length=20, choices=Types.choices, default=Types.SUBSCRIPTION, db_index=True
    )
    sales_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=["product_type", "is_active"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(sales_price__gte=0) & Q(cost_price__gte=0),
                name="product_prices_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ProductVariant(models.Model):
    """A variant of a product (e.g. the 'Odoo' brand) whose adjustment is added
    to the product's sales price."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=200)
    price_adjustment = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"], name="variant_name_unique_per_product"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} — {self.name}"


class Plan(models.Model):
    """A subscription plan: what it costs, how often it bills, and which actions
    it permits — the admin decides the flags plan by plan."""

    class BillingPeriods(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    billing_period = models.CharField(
        max_length=20, choices=BillingPeriods.choices, db_index=True
    )
    min_quantity = models.PositiveIntegerField(default=1)
    available_from = models.DateField(null=True, blank=True)
    available_until = models.DateField(null=True, blank=True)

    # Behaviour flags — the admin decides these plan by plan
    auto_close_on_end = models.BooleanField(
        default=False, help_text="Close automatically when the plan ends"
    )
    allow_close_early = models.BooleanField(
        default=True, help_text="Subscriptions may be closed before their expiry date"
    )
    allow_pause = models.BooleanField(
        default=True, help_text="Subscriptions may be paused"
    )
    allow_renewal = models.BooleanField(
        default=True, help_text="Subscriptions may be renewed after expiry"
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=["billing_period", "is_active"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="plan_price_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(available_from__isnull=True)
                | Q(available_until__isnull=True)
                | Q(available_from__lte=models.F("available_until")),
                name="plan_availability_window_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_billing_period_display()})"

    def is_available_on(self, day) -> bool:
        if not self.is_active:
            return False
        if self.available_from and day < self.available_from:
            return False
        if self.available_until and day > self.available_until:
            return False
        return True


class TaxRule(models.Model):
    """Admin-configured tax rule. A rule applying to a specific product takes
    priority over a global one (null applies_to = all products); ties break by
    higher rate."""

    name = models.CharField(max_length=200)
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="As a fraction, e.g. 0.1500 for 15%",
    )
    applies_to = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tax_rules",
        help_text="Leave empty to apply to all products",
    )
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-priority", "name")

    def __str__(self) -> str:
        target = self.applies_to.name if self.applies_to else "all products"
        return f"{self.name} ({self.rate:.2%} on {target})"
