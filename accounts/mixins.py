"""Re-export the shared role mixins so accounts-specific views import locally.

The canonical implementations live in core.mixins (single source of truth for
role gating across all apps).
"""
from core.mixins import (  # noqa: F401
    AdminRequiredMixin,
    CustomerRequiredMixin,
    RoleRequiredMixin,
    StaffRequiredMixin,
)
