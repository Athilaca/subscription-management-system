from django import forms
from django.forms import inlineformset_factory

from accounts.models import User
from catalog.models import ProductVariant
from subscriptions.models import (
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
)


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = (
            "customer",
            "plan",
            "quantity",
            "start_date",
            "expiry_date",
            "payment_terms_days",
            "owner",
            "valid_until",
            "notes",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = User.objects.filter(role=User.Roles.CUSTOMER)
        self.fields["owner"].queryset = User.objects.filter(
            role__in=(User.Roles.ADMIN, User.Roles.STAFF)
        )

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get("plan")
        start_date = cleaned.get("start_date")
        if plan and start_date and not plan.is_available_on(start_date):
            self.add_error("start_date", "The plan is not available on this start date.")
        if plan and cleaned.get("quantity") and cleaned["quantity"] < plan.min_quantity:
            self.add_error(
                "quantity",
                f"This plan requires a minimum quantity of {plan.min_quantity}.",
            )
        return cleaned


class SubscriptionLineForm(forms.ModelForm):
    variants = forms.ModelMultipleChoiceField(
        queryset=ProductVariant.objects.select_related("product"),
        required=False,
        help_text="Variants adjust the unit price (Ctrl/Cmd-click to choose)",
    )

    class Meta:
        model = SubscriptionLine
        fields = ("product", "quantity")

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        variants = cleaned.get("variants")
        if product and variants:
            foreign = [v for v in variants if v.product_id != product.id]
            if foreign:
                self.add_error(
                    "variants",
                    "All selected variants must belong to the line's product.",
                )
        return cleaned


SubscriptionLineFormSet = inlineformset_factory(
    Subscription,
    SubscriptionLine,
    form=SubscriptionLineForm,
    extra=3,
    can_delete=True,
)


class QuotationTemplateForm(forms.ModelForm):
    class Meta:
        model = QuotationTemplate
        fields = ("name", "plan", "validity_days", "notes", "is_active")
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class QuotationTemplateLineForm(forms.ModelForm):
    class Meta:
        model = QuotationTemplateLine
        fields = ("product", "quantity", "sort_order")


QuotationTemplateLineFormSet = inlineformset_factory(
    QuotationTemplate,
    QuotationTemplateLine,
    form=QuotationTemplateLineForm,
    extra=3,
    can_delete=True,
)
