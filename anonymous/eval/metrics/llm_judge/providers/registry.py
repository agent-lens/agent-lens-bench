from typing import Dict, Final

# NOTE: keep this module lightweight; it should not import SDKs.

PROVIDER_GEMINI: Final[str] = "gemini"
PROVIDER_ANTHROPIC: Final[str] = "anthropic"
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_OPENAI_COMPATIBLE: Final[str] = "openai_compatible"

_KNOWN_PROVIDERS: Final[set[str]] = {
    PROVIDER_GEMINI,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    PROVIDER_OPENAI_COMPATIBLE,
}


def get_judge_provider(config_dict: Dict) -> str:
    """Return the configured judge transport.

    The provider is selected explicitly via the `judge_provider` config key,
    independently from `judge_model` (which is just the model identifier passed
    verbatim to the underlying API).
    """
    raw = str(config_dict.get("judge_provider") or "").strip().lower()
    if raw not in _KNOWN_PROVIDERS:
        raise ValueError(
            f"Invalid or missing judge_provider: {raw!r}. "
            f"Expected one of {sorted(_KNOWN_PROVIDERS)}."
        )
    return raw
