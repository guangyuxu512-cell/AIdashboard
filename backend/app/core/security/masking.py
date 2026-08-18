def mask_login_identifier(value: str) -> str:
    value = value.strip()
    if "@" in value:
        local_part, domain = value.rsplit("@", 1)
        visible = local_part[:3] if len(local_part) >= 3 else local_part[:1]
        return f"{visible}***@{domain}"

    if value.isdigit() and len(value) >= 7:
        return f"{value[:3]}****{value[-4:]}"

    if len(value) <= 2:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"
