import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexityValidator:
    """Brightloop password policy: uppercase, lowercase and a special character.

    (Minimum length is enforced separately by MinimumLengthValidator with
    min_length=9 — the brief requires "more than eight characters".)
    """

    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("The password must contain at least one uppercase letter."),
                code="password_missing_uppercase",
            )
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("The password must contain at least one lowercase letter."),
                code="password_missing_lowercase",
            )
        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValidationError(
                _("The password must contain at least one special character."),
                code="password_missing_special",
            )

    def get_help_text(self):
        return _(
            "Your password must contain an uppercase letter, a lowercase letter "
            "and a special character."
        )
