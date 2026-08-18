import hashlib
import hmac
import secrets


WORKER_TOKEN_PREFIX = "ccw_"


def generate_worker_token() -> str:
    return f"{WORKER_TOKEN_PREFIX}{secrets.token_urlsafe(48)}"


def hash_worker_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_worker_token(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_worker_token(token), expected_hash)
