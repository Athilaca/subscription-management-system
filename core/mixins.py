from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from accounts.models import User


class RoleRequiredMixin(LoginRequiredMixin):
    """Allow access only to authenticated users whose role is in ``allowed_roles``."""

    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)
        raise PermissionDenied


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Roles.ADMIN,)


class StaffRequiredMixin(RoleRequiredMixin):
    """Admin and staff share the back-office; admin-only areas use AdminRequiredMixin."""

    allowed_roles = (User.Roles.ADMIN, User.Roles.STAFF)


class CustomerRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Roles.CUSTOMER,)
