from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/new/", views.ProductCreateView.as_view(), name="product-create"),
    path("products/<int:pk>/edit/", views.ProductUpdateView.as_view(), name="product-update"),
    path("products/<int:pk>/delete/", views.ProductDeleteView.as_view(), name="product-delete"),
    path("plans/", views.PlanListView.as_view(), name="plan-list"),
    path("plans/new/", views.PlanCreateView.as_view(), name="plan-create"),
    path("plans/<int:pk>/edit/", views.PlanUpdateView.as_view(), name="plan-update"),
    path("plans/<int:pk>/delete/", views.PlanDeleteView.as_view(), name="plan-delete"),
    path("tax-rules/", views.TaxRuleListView.as_view(), name="taxrule-list"),
    path("tax-rules/new/", views.TaxRuleCreateView.as_view(), name="taxrule-create"),
    path("tax-rules/<int:pk>/edit/", views.TaxRuleUpdateView.as_view(), name="taxrule-update"),
    path("tax-rules/<int:pk>/delete/", views.TaxRuleDeleteView.as_view(), name="taxrule-delete"),
]
