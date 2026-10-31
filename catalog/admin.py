from django.contrib import admin

from catalog.models import Plan, Product, ProductVariant, TaxRule


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "sales_price", "cost_price", "is_active")
    list_filter = ("product_type", "is_active")
    search_fields = ("name",)
    inlines = [ProductVariantInline]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "billing_period",
        "price",
        "min_quantity",
        "auto_close_on_end",
        "allow_close_early",
        "allow_pause",
        "allow_renewal",
        "is_active",
    )
    list_filter = ("billing_period", "is_active")
    search_fields = ("name",)


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "rate", "applies_to", "priority", "is_active")
    list_filter = ("is_active",)
