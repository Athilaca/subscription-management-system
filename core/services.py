"""Shared services: gap-free document numbering under concurrency."""
from django.db import transaction


def allocate_number(key: str, prefix: str = "", width: int = 6) -> str:
    """Atomically draw the next sequential number, e.g. allocate_number("subscription", "SUB-") -> "SUB-000001".

    Must be called while saving the owning document; the row lock serialises
    concurrent allocators so numbers are unique and gap-free per key.
    """
    from core.models import NumberSequence

    with transaction.atomic():
        sequence, _created = NumberSequence.objects.select_for_update().get_or_create(
            key=key
        )
        number = sequence.next_number
        sequence.next_number = number + 1
        sequence.save()
    return f"{prefix}{number:0{width}d}"
