from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)

from accounts.mixins import AdminRequiredMixin, CustomerRequiredMixin, StaffRequiredMixin
from subscriptions import services
from subscriptions.forms import (
    QuotationTemplateForm,
    QuotationTemplateLineFormSet,
    SubscriptionForm,
    SubscriptionLineFormSet,
)
from subscriptions.models import (
    LineVariant,
    QuotationTemplate,
    Subscription,
)

EDITABLE_STATUSES = (Subscription.Status.DRAFT, Subscription.Status.QUOTATION)


# --- Subscription formset plumbing ----------------------------------------------------

class SubscriptionFormMixin:
    """Subscriptions edit together with their product lines (inline formset).

    Line variants are chosen through the form's ``variants`` field and stored
    through LineVariant with the price adjustment snapshotted.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_formset"] = SubscriptionLineFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_formset"] = SubscriptionLineFormSet(instance=self.object)
        return context

    def _sync_line_variants(self, formset):
        for form in formset.forms:
            line = form.instance
            if line.pk is None or form.cleaned_data.get("DELETE"):
                continue
            chosen = form.cleaned_data.get("variants") or []
            current = {sel.variant_id: sel for sel in line.variant_selections.all()}
            for variant in chosen:
                selection = current.pop(variant.id, None)
                if selection is None:
                    LineVariant.objects.create(
                        line=line, variant=variant, price_adjustment=variant.price_adjustment
                    )
            for stale in current.values():
                stale.delete()

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["line_formset"]
        if not formset.is_valid():
            return self.render_to_response(context)
        response = super().form_valid(form)
        formset.instance = self.object
        formset.save()
        self._sync_line_variants(formset)
        services.recalculate_subscription(self.object)
        messages.success(self.request, f"Subscription {self.object.number} saved.")
        return response


class SubscriptionCreateView(StaffRequiredMixin, SubscriptionFormMixin, CreateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = "subscriptions/subscription_form.html"
    success_url = reverse_lazy("subscriptions:subscription-list")

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("owner", self.request.user)
        # ?template=<id> prefills from a quotation template (S3.1)
        template_id = self.request.GET.get("template")
        if template_id:
            template = get_object_or_404(
                QuotationTemplate, pk=template_id, is_active=True
            )
            initial["plan"] = template.plan
            initial["notes"] = f"Created from template “{template.name}”."
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template_id = self.request.GET.get("template")
        if template_id and self.request.method == "GET":
            template = get_object_or_404(QuotationTemplate, pk=template_id, is_active=True)
            context["line_formset"] = SubscriptionLineFormSet(
                initial=[
                    {"product": line.product, "quantity": line.quantity}
                    for line in template.lines.select_related("product")
                ]
            )
            context["template_name"] = template.name
        return context


class SubscriptionUpdateView(StaffRequiredMixin, SubscriptionFormMixin, UpdateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = "subscriptions/subscription_form.html"
    success_url = reverse_lazy("subscriptions:subscription-list")

    def dispatch(self, request, *args, **kwargs):
        sub = self.get_object()
        if sub.status not in EDITABLE_STATUSES:
            messages.error(
                request,
                "Only draft or quotation subscriptions can be edited.",
            )
            return redirect("subscriptions:subscription-detail", pk=sub.pk)
        return super().dispatch(request, *args, **kwargs)


class SubscriptionDeleteView(StaffRequiredMixin, DeleteView):
    model = Subscription
    template_name = "subscriptions/subscription_confirm_delete.html"
    success_url = reverse_lazy("subscriptions:subscription-list")

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().status != Subscription.Status.DRAFT:
            messages.error(request, "Only draft subscriptions can be deleted.")
            return redirect("subscriptions:subscription-detail", pk=self.get_object().pk)
        return super().dispatch(request, *args, **kwargs)


class SubscriptionListView(StaffRequiredMixin, ListView):
    model = Subscription
    template_name = "subscriptions/subscription_list.html"
    context_object_name = "subscriptions"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            Subscription.objects.select_related("customer", "plan", "owner")
            .prefetch_related("lines__product")
        )
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)
        customer_id = self.request.GET.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        search = self.request.GET.get("q")
        if search:
            queryset = queryset.filter(
                Q(number__icontains=search) | Q(customer__email__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Subscription.Status.choices
        context["current_status"] = self.request.GET.get("status", "")
        context["search"] = self.request.GET.get("q", "")
        return context


class SubscriptionDetailView(StaffRequiredMixin, DetailView):
    model = Subscription
    template_name = "subscriptions/subscription_detail.html"
    context_object_name = "subscription"

    def get_queryset(self):
        return Subscription.objects.select_related(
            "customer", "plan", "owner"
        ).prefetch_related("lines__product", "lines__variant_selections__variant")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allowed_actions"] = services.allowed_actions(self.object)
        context["can_renew"] = (
            self.object.status == Subscription.Status.CLOSED
            and self.object.plan.allow_renewal
            and self.object.expiry_date is not None
        )
        return context


class SubscriptionTransitionView(StaffRequiredMixin, View):
    """POST-only guarded state transitions (S3.3)."""

    def post(self, request, pk, new_status):
        sub = get_object_or_404(Subscription, pk=pk)
        try:
            if sub.status == Subscription.Status.PAUSED and new_status == (
                Subscription.Status.ACTIVE
            ):
                services.resume(sub)
            else:
                services.transition(sub, new_status)
            messages.success(
                request,
                f"Subscription {sub.number} is now “{sub.get_status_display()}”.",
            )
        except services.InvalidTransition as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("subscriptions:subscription-detail", pk=sub.pk)


class SubscriptionRenewView(StaffRequiredMixin, View):
    def post(self, request, pk):
        sub = get_object_or_404(Subscription, pk=pk)
        try:
            renewal = services.create_renewal(sub)
            messages.success(request, f"Renewal created: {renewal.number}.")
            return redirect("subscriptions:subscription-detail", pk=renewal.pk)
        except services.InvalidTransition as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("subscriptions:subscription-detail", pk=sub.pk)


# --- Quotation templates (admin manages, staff read & use) ----------------------------

class QuotationTemplateListView(StaffRequiredMixin, ListView):
    model = QuotationTemplate
    template_name = "subscriptions/quotation_template_list.html"
    context_object_name = "templates"
    queryset = QuotationTemplate.objects.prefetch_related("lines__product")
    paginate_by = 25


class QuotationTemplateFormMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_formset"] = QuotationTemplateLineFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_formset"] = QuotationTemplateLineFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["line_formset"]
        if not formset.is_valid():
            return self.render_to_response(context)
        if not self.object.pk:
            form.instance.created_by = self.request.user
        response = super().form_valid(form)
        formset.instance = self.object
        formset.save()
        messages.success(self.request, f"Template “{self.object.name}” saved.")
        return response


class QuotationTemplateCreateView(AdminRequiredMixin, QuotationTemplateFormMixin, CreateView):
    model = QuotationTemplate
    form_class = QuotationTemplateForm
    template_name = "subscriptions/quotation_template_form.html"
    success_url = reverse_lazy("subscriptions:template-list")


class QuotationTemplateUpdateView(AdminRequiredMixin, QuotationTemplateFormMixin, UpdateView):
    model = QuotationTemplate
    form_class = QuotationTemplateForm
    template_name = "subscriptions/quotation_template_form.html"
    success_url = reverse_lazy("subscriptions:template-list")


class QuotationTemplateDeleteView(AdminRequiredMixin, DeleteView):
    model = QuotationTemplate
    template_name = "subscriptions/quotation_template_confirm_delete.html"
    success_url = reverse_lazy("subscriptions:template-list")


# --- Customer portal (read-only, auto-filtered to the signed-in customer) -------------

class PortalSubscriptionListView(CustomerRequiredMixin, ListView):
    model = Subscription
    template_name = "subscriptions/portal_subscription_list.html"
    context_object_name = "subscriptions"
    paginate_by = 25

    def get_queryset(self):
        return (
            Subscription.objects.filter(customer=self.request.user)
            .select_related("plan")
            .prefetch_related("lines__product")
        )


class PortalSubscriptionDetailView(CustomerRequiredMixin, DetailView):
    model = Subscription
    template_name = "subscriptions/portal_subscription_detail.html"
    context_object_name = "subscription"

    def get_object(self, queryset=None):
        sub = get_object_or_404(
            Subscription.objects.select_related("plan").prefetch_related(
                "lines__product", "lines__variant_selections__variant"
            ),
            pk=self.kwargs["pk"],
            customer=self.request.user,  # portal never leaks other customers' data
        )
        return sub
