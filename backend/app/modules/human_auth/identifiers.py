LOGIN_NAME_MAX_LENGTH = 100


def normalize_login_name(value: str) -> str:
    """将内部登录账号收口为可持久化、大小写不敏感的稳定形式。"""

    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("登录账号不能为空")
    if len(normalized) > LOGIN_NAME_MAX_LENGTH:
        raise ValueError(f"登录账号不能超过{LOGIN_NAME_MAX_LENGTH}个字符")
    if any(character.isspace() for character in normalized):
        raise ValueError("登录账号不能包含空白字符")
    return normalized
