from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShadowBotApiEnvelope:
    code: int
    data: Any


def normalize_shadowbot_api_envelope(payload: Any) -> ShadowBotApiEnvelope:
    """Normalize the two envelope casings observed from ShadowBot 6.3.6."""
    if not isinstance(payload, dict):
        raise ValueError("ShadowBot response must be an object")

    code = _required_case_variant(payload, "code", "Code")
    data = _required_case_variant(payload, "data", "Data")
    if isinstance(code, bool) or not isinstance(code, int):
        raise ValueError("ShadowBot response code must be an integer")
    return ShadowBotApiEnvelope(code=code, data=data)


def _required_case_variant(
    payload: dict[str, Any],
    lower_key: str,
    upper_key: str,
) -> Any:
    present = [key for key in (lower_key, upper_key) if key in payload]
    if not present:
        raise ValueError(f"ShadowBot response is missing {lower_key}/{upper_key}")
    if len(present) == 2 and payload[lower_key] != payload[upper_key]:
        raise ValueError(
            f"ShadowBot response has conflicting {lower_key}/{upper_key} values",
        )
    return payload[present[0]]
