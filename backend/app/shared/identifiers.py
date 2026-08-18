from uuid import UUID, uuid4


def generate_id() -> UUID:
    """Generate the single UUID form used by all core domain identifiers."""

    return uuid4()
