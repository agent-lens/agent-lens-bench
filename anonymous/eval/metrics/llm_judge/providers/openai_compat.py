import os
import threading
import uuid
from typing import Any, Dict, Final

from openai import OpenAI

from anonymous.eval.metrics.llm_judge.providers.registry import (
    PROVIDER_OPENAI,
    PROVIDER_OPENAI_COMPATIBLE,
)

ENV_OPENAI_BASE_URL: Final[str] = "OPENAI_BASE_URL"
X_DEVICE_ID_HEADER: Final[str] = "X-Device-ID"
_thread_local = threading.local()


def _get_thread_device_id() -> str:
    """Return a UUID4 device id unique to the calling thread (lazy)."""
    device_id = getattr(_thread_local, "device_id", None)
    if device_id is None:
        device_id = str(uuid.uuid4())
        _thread_local.device_id = device_id
    return device_id


def resolve_openai_compatible_base_url(config_dict: Dict) -> str:
    """Resolve the OpenAI-compatible base URL.

    Priority:
      1. env `OPENAI_BASE_URL`
      2. config `openai_compatible.base_url`
      3. "" (empty)

    Only meaningful for `judge_provider == openai_compatible`. The `openai`
    provider always targets public OpenAI and does not consult this resolver.
    """
    env_value = str(os.getenv(ENV_OPENAI_BASE_URL) or "").strip()
    if env_value:
        return env_value
    cfg_value = (config_dict.get("openai_compatible") or {}).get("base_url") or ""
    return str(cfg_value).strip()


def _user_request_kwargs(config_dict: Dict, provider: str) -> Dict[str, Any]:
    section_key = "openai" if provider == PROVIDER_OPENAI else "openai_compatible"
    section = config_dict.get(section_key) or {}
    return dict(section.get("request_kwargs") or {})


def get_openai_compatible_response(
    config_dict: Dict,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    *,
    provider: str,
    failed_with_flex_tier: bool = False,
) -> Any:
    """Call OpenAI / OpenAI-compatible chat.completions endpoint.

    `provider` selects between:
      - `openai`            -> public OpenAI (api.openai.com); api_key is required;
                               adds flex-tier defaults.
      - `openai_compatible` -> custom backend; base_url is required (env OPENAI_BASE_URL
                               or `openai_compatible.base_url`); api_key may be empty.

    User-provided `<section>.request_kwargs` is merged on top of built-in defaults
    (user values win), so callers can pass `temperature`, provider flags, etc.
    """
    judge_model = config_dict["judge_model"]

    request_kwargs: Dict[str, Any] = {
        "model": judge_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": config_dict["max_completion_tokens"],
        "reasoning_effort": config_dict["reasoning_effort"],
    }

    default_headers = {X_DEVICE_ID_HEADER: _get_thread_device_id()}

    if provider == PROVIDER_OPENAI:
        if not api_key:
            raise ValueError("api_key is required for the 'openai' provider")
        client = OpenAI(api_key=api_key, default_headers=default_headers)
        request_kwargs["service_tier"] = (
            "flex"
            if (
                config_dict["prefer_flex_service_tier"]
                and judge_model in ("o4-mini",)
                and not failed_with_flex_tier
            )
            else "default"
        )
    elif provider == PROVIDER_OPENAI_COMPATIBLE:
        base_url = resolve_openai_compatible_base_url(config_dict)
        if not base_url:
            raise ValueError(
                "base_url is required for the 'openai_compatible' provider: "
                "set env OPENAI_BASE_URL or openai_compatible.base_url"
            )
        client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
            default_headers=default_headers,
        )
    else:
        raise ValueError(f"Unsupported provider for OpenAI SDK call: {provider!r}")

    request_kwargs.update(_user_request_kwargs(config_dict, provider))

    response = client.chat.completions.create(**request_kwargs)

    # Strip reasoning preamble for backends that emit it (e.g. `<think>...</think>`
    # from DeepSeek-R1 / Qwen-QwQ via OpenAI-compatible transport).
    if provider == PROVIDER_OPENAI_COMPATIBLE:
        separator = str(config_dict.get("judge_model_reasoning_separator") or "")
        if separator:
            content = response.choices[0].message.content
            if content and separator in content:
                response.choices[0].message.content = content.split(separator)[-1]

    return response
