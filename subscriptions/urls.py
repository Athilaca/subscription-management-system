from django.urls import path

from subscriptions import views

app_name = "subscriptions"

urlpatterns = [
    # Back-office (staff)
    path("subscriptions/", views.SubscriptionListView.as_view(), name="subscription-list"),
    path("subscriptions/new/", views.SubscriptionCreateView.as_view(), name="subscription-create"),
    path("subscriptions/<int:pk>/", views.SubscriptionDetailView.as_view(), name="subscription-detail"),
    path("subscriptions/<int:pk>/edit/", views.SubscriptionUpdateView.as_view(), name="subscription-update"),
    path("subscriptions/<int:pk>/delete/", views.SubscriptionDeleteView.as_view(), name="subscription-delete"),
    path("subscriptions/<int:pk>/transition/<str:new_status>/", views.SubscriptionTransitionView.as_view(), name="subscription-transition"),
    path("subscriptions/<int:pk>/renew/", views.SubscriptionRenewView.as_view(), name="subscription-renew"),
    # Quotation templates
    path("quote-templates/", views.QuotationTemplateListView.as_view(), name="template-list"),
    path("quote-templates/new/", views.QuotationTemplateCreateView.as_view(), name="template-create"),
    path("quote-templates/<int:pk>/edit/", views.QuotationTemplateUpdateView.as_view(), name="template-update"),
    path("quote-templates/<int:pk>/delete/", views.QuotationTemplateDeleteView.as_view(), name="template-delete"),
    # Customer portal (read-only)
    path("portal/subscriptions/", views.PortalSubscriptionListView.as_view(), name="portal-subscription-list"),
    path("portal/subscriptions/<int:pk>/", views.PortalSubscriptionDetailView.as_view(), name="portal-subscription-detail"),
]
