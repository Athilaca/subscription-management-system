from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager


class User(AbstractUser):
    """Email-based user with a Brightloop role.

    Customers sign themselves up; only admins can create staff accounts; the
    superuser/createsuperuser path always yields an admin.
    """

    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"
        CUSTOMER = "customer", "Customer"

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CUSTOMER,
        db_index=True,
    )
    phone = models.CharField(max_length=32, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(role="") & models.Q(role__isnull=False),
                name="user_role_required",
            ),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def is_admin(self) -> bool:
        return self.role == self.Roles.ADMIN

    @property
    def is_staff_member(self) -> bool:
        return self.role in (self.Roles.ADMIN, self.Roles.STAFF)
