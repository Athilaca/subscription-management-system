from django.contrib import admin

from subscriptions.models import (
    LineVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
)


class SubscriptionLineInline(admin.TabularInline):
    model = SubscriptionLine
    extra = 1
    show_change_link = True


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "customer",
        "plan",
        "status",
        "start_date",
        "expiry_date",
        "next_billing_date",
        "owner",
    )
    list_filter = ("status", "plan")
    search_fields = ("number", "customer__email")
    readonly_fields = ("number", "next_billing_date")
    inlines = [SubscriptionLineInline]


class QuotationTemplateLineInline(admin.TabularInline):
    model = QuotationTemplateLine
    extra = 1


@admin.register(QuotationTemplate)
class QuotationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "plan", "validity_days", "is_active")
    inlines = [QuotationTemplateLineInline]


admin.site.register(SubscriptionLine)
admin.site.register(LineVariant)
