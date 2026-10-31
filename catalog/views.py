from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from accounts.mixins import AdminRequiredMixin, StaffRequiredMixin
from catalog.forms import PlanForm, ProductForm, TaxRuleForm, VariantFormSet
from catalog.models import Plan, Product, TaxRule


# --- Products (staff browse; admin edits) --------------------------------------------

class ProductListView(StaffRequiredMixin, ListView):
    model = Product
    template_name = "catalog/product_list.html"
    context_object_name = "products"
    queryset = Product.objects.prefetch_related("variants")
    paginate_by = 25


class ProductFormMixin:
    """Products edit together with their variant rows (inline formset)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["variant_formset"] = VariantFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["variant_formset"] = VariantFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["variant_formset"]
        if formset.is_valid():
            response = super().form_valid(form)
            formset.instance = self.object
            formset.save()
            messages.success(self.request, f"Product “{self.object.name}” saved.")
            return response
        return self.render_to_response(context)


class ProductCreateView(AdminRequiredMixin, ProductFormMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_url = reverse_lazy("catalog:product-list")


class ProductUpdateView(AdminRequiredMixin, ProductFormMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_url = reverse_lazy("catalog:product-list")


class ProductDeleteView(AdminRequiredMixin, DeleteView):
    model = Product
    template_name = "catalog/product_confirm_delete.html"
    success_url = reverse_lazy("catalog:product-list")


# --- Plans ---------------------------------------------------------------------------

class PlanListView(StaffRequiredMixin, ListView):
    model = Plan
    template_name = "catalog/plan_list.html"
    context_object_name = "plans"
    paginate_by = 25


class PlanCreateView(AdminRequiredMixin, CreateView):
    model = Plan
    form_class = PlanForm
    template_name = "catalog/plan_form.html"
    success_url = reverse_lazy("catalog:plan-list")

    def form_valid(self, form):
        messages.success(self.request, f"Plan “{form.instance.name}” created.")
        return super().form_valid(form)


class PlanUpdateView(AdminRequiredMixin, UpdateView):
    model = Plan
    form_class = PlanForm
    template_name = "catalog/plan_form.html"
    success_url = reverse_lazy("catalog:plan-list")

    def form_valid(self, form):
        messages.success(self.request, f"Plan “{form.instance.name}” saved.")
        return super().form_valid(form)


class PlanDeleteView(AdminRequiredMixin, DeleteView):
    model = Plan
    template_name = "catalog/plan_confirm_delete.html"
    success_url = reverse_lazy("catalog:plan-list")


# --- Tax rules -----------------------------------------------------------------------

class TaxRuleListView(StaffRequiredMixin, ListView):
    model = TaxRule
    template_name = "catalog/taxrule_list.html"
    context_object_name = "tax_rules"
    queryset = TaxRule.objects.select_related("applies_to")
    paginate_by = 25


class TaxRuleCreateView(AdminRequiredMixin, CreateView):
    model = TaxRule
    form_class = TaxRuleForm
    template_name = "catalog/taxrule_form.html"
    success_url = reverse_lazy("catalog:taxrule-list")

    def form_valid(self, form):
        messages.success(self.request, f"Tax rule “{form.instance.name}” created.")
        return super().form_valid(form)


class TaxRuleUpdateView(AdminRequiredMixin, UpdateView):
    model = TaxRule
    form_class = TaxRuleForm
    template_name = "catalog/taxrule_form.html"
    success_url = reverse_lazy("catalog:taxrule-list")

    def form_valid(self, form):
        messages.success(self.request, f"Tax rule “{form.instance.name}” saved.")
        return super().form_valid(form)


class TaxRuleDeleteView(AdminRequiredMixin, DeleteView):
    model = TaxRule
    template_name = "catalog/taxrule_confirm_delete.html"
    success_url = reverse_lazy("catalog:taxrule-list")
