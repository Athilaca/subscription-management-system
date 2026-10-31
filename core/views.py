from django.views.generic import TemplateView

from core.mixins import LoginRequiredMixin


class HomeView(LoginRequiredMixin, TemplateView):
    """Placeholder landing page; replaced by the dashboard in Sprint 5."""

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Home"
        return context
