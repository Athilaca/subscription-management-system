from django.db import models


class NumberSequence(models.Model):
    """Backing store for document numbering (subscriptions, invoices).

    Rows are locked with select_for_update at allocation time so concurrent
    requests can never draw the same number.
    """

    key = models.CharField(max_length=50, unique=True)
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return f"{self.key} (next: {self.next_number})"
