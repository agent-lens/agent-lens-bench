import logging
from time import sleep
from typing import Any, Dict, Tuple

import anthropic
from openai import APIConnectionError, APIError, RateLimitError

from anonymous.eval.metrics.llm_judge.providers.anthropic_provider import (
    get_anthropic_response,
)
from anonymous.eval.metrics.llm_judge.providers.gemini_provider import (
    get_gemini_response,
)
from anonymous.eval.metrics.llm_judge.providers.openai_compat import (
    get_openai_compatible_response,
)
from anonymous.eval.metrics.llm_judge.providers.registry import PROVIDER_OPENAI

LOG = logging.getLogger(__name__)


def call_gemini(
    *, config_dict: Dict, system_prompt: str, user_prompt: str, api_key: str
) -> Tuple[str, int, int, int]:
    response = get_gemini_response(config_dict, system_prompt, user_prompt, api_key)
    content = response.text if response.text else ""
    prompt_tokens = response.usage_metadata.prompt_token_count
    completion_tokens = response.usage_metadata.total_token_count - prompt_tokens
    return content, prompt_tokens, completion_tokens, 0


def call_anthropic_with_retry(
    *,
    config_dict: Dict,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    max_retries: int = 12,
    delay_seconds: int = 10,
) -> Tuple[str, int, int, int]:
    last_err = None
    for _ in range(max_retries):
        try:
            response = get_anthropic_response(
                config_dict,
                system_prompt,
                user_prompt,
                api_key,
            )
            content = response.content[-1].text
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            return content, prompt_tokens, completion_tokens, 0
        except anthropic.RateLimitError as e:
            last_err = e
            LOG.info(
                "Failed to call LLM API: %s, retrying in %s seconds...",
                e,
                delay_seconds,
            )
            sleep(delay_seconds)

    raise RuntimeError("Anthropic rate-limited after multiple retries") from last_err


def _extract_openai_cached_prompt_tokens(response: Any) -> int:
    """Best-effort extraction of OpenAI prompt-caching token count.

    OpenAI chat.completions may include:
      response.usage.prompt_tokens_details.cached_tokens
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0

    details = getattr(usage, "prompt_tokens_details", None)
    if details is None and isinstance(usage, dict):
        details = usage.get("prompt_tokens_details")

    if details is None:
        return 0

    if isinstance(details, dict):
        val = details.get("cached_tokens")
        return int(val) if val is not None else 0

    val = getattr(details, "cached_tokens", None)
    return int(val) if val is not None else 0


def _extract_openai_content(response: Any) -> str:
    """Extract message content from an OpenAI-compatible response.
    It's equivalent to code: `response.choices[0].message.content`.

    Some providers occasionally return responses with missing fields
    (e.g. ``choices`` or ``message.content`` set to None). Validate the
    structure and raise ValueError so the caller can retry.
    """
    if response is None:
        raise ValueError("LLM provider returned None response")
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("LLM provider returned response with no choices")
    message = getattr(choices[0], "message", None)
    if message is None:
        raise ValueError("LLM provider returned choice with no message")
    content = getattr(message, "content", None)
    if content is None:
        raise ValueError("LLM provider returned message with None content")
    return content


def call_openai_compatible_with_retry(
    *,
    config_dict: Dict,
    provider: str,
    system_prompt: str,
    user_prompt: str,
    failed_with_flex_tier: bool,
    api_key: str,
    max_retries: int = 2,
) -> Tuple[str, int, int, int, bool]:
    for _ in range(max_retries):
        try:
            response = get_openai_compatible_response(
                config_dict,
                system_prompt,
                user_prompt,
                api_key,
                provider=provider,
                failed_with_flex_tier=failed_with_flex_tier,
            )
            content = _extract_openai_content(response)
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            cached_prompt_tokens = _extract_openai_cached_prompt_tokens(response)
            return (
                content,
                prompt_tokens,
                completion_tokens,
                cached_prompt_tokens,
                failed_with_flex_tier,
            )
        except (RateLimitError, APIError, APIConnectionError, ValueError) as e:
            if provider == PROVIDER_OPENAI:
                if failed_with_flex_tier:
                    raise RuntimeError(f"Failed to call LLM API: {e}") from e
                failed_with_flex_tier = True
                LOG.info(
                    "Failed to call LLM API on flex service tier: %s, retrying on default tier...",
                    e,
                )
            else:
                LOG.info("Failed to call LLM API: %s, retrying...", e)

    raise RuntimeError("OpenAI-compatible call failed after retries")
