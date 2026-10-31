from django import forms
from django.forms import inlineformset_factory

from catalog.models import Plan, Product, ProductVariant, TaxRule


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "product_type", "sales_price", "cost_price", "notes", "is_active")


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ("name", "price_adjustment")


VariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=2,
    can_delete=True,
)


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = (
            "name",
            "description",
            "price",
            "billing_period",
            "min_quantity",
            "available_from",
            "available_until",
            "auto_close_on_end",
            "allow_close_early",
            "allow_pause",
            "allow_renewal",
            "is_active",
        )
        widgets = {
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "available_until": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class TaxRuleForm(forms.ModelForm):
    class Meta:
        model = TaxRule
        fields = ("name", "rate", "applies_to", "priority", "is_active")
