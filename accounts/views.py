from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from accounts.forms import SignupForm, StaffCreateForm
from accounts.mixins import AdminRequiredMixin
from accounts.models import User


class SignupView(CreateView):
    """Public customer signup (staff are created by admins, not by signing up)."""

    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Account created — you can now sign in.",
        )
        return response


class StaffListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/staff_list.html"
    context_object_name = "staff_members"
    queryset = User.objects.filter(role=User.Roles.STAFF).order_by("email")
    paginate_by = 25


class StaffCreateView(AdminRequiredMixin, CreateView):
    """Only admins can add internal staff — enforced here and by the template nav."""

    model = User
    form_class = StaffCreateForm
    template_name = "accounts/staff_form.html"
    success_url = reverse_lazy("accounts:staff-list")

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Staff account created for {form.instance.email}.",
        )
        return super().form_valid(form)
