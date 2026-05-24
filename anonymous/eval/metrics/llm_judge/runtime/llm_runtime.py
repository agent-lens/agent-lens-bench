import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Tuple

import tqdm

from anonymous.eval.metrics.llm_judge.providers.registry import (
    PROVIDER_ANTHROPIC,
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_OPENAI_COMPATIBLE,
)
from anonymous.eval.metrics.llm_judge.runtime.provider_policies import (
    call_anthropic_with_retry,
    call_gemini,
    call_openai_compatible_with_retry,
)

LOG = logging.getLogger(__name__)


def _is_prompt_too_long_error(err: BaseException) -> bool:
    msg = str(err).lower()
    return (
        "please reduce the length of the messages" in msg
        or "input tokens exceed the configured limit" in msg
    )


def call_llm_with_retry_policy(
    *,
    config_dict: Dict,
    provider: str,
    system_prompt: str,
    user_prompt: str,
    failed_with_flex_tier: bool,
    api_key: str,
) -> Tuple[str, int, int, int, bool]:
    """Call the configured provider and return (content, prompt_tokens, completion_tokens, cached_prompt_tokens, failed_with_flex_tier).

    `failed_with_flex_tier` is a mutable run-local state: if flex tier fails once,
    subsequent calls should use default tier.

    This function is allowed to raise on unexpected errors.
    """
    try:
        if provider == PROVIDER_GEMINI:
            content, prompt_tokens, completion_tokens, cached_prompt_tokens = (
                call_gemini(
                    config_dict=config_dict,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    api_key=api_key,
                )
            )
            return (
                content,
                prompt_tokens,
                completion_tokens,
                cached_prompt_tokens,
                failed_with_flex_tier,
            )

        if provider == PROVIDER_ANTHROPIC:
            content, prompt_tokens, completion_tokens, cached_prompt_tokens = (
                call_anthropic_with_retry(
                    config_dict=config_dict,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    api_key=api_key,
                )
            )
            return (
                content,
                prompt_tokens,
                completion_tokens,
                cached_prompt_tokens,
                failed_with_flex_tier,
            )

        if provider in (PROVIDER_OPENAI, PROVIDER_OPENAI_COMPATIBLE):
            return call_openai_compatible_with_retry(
                config_dict=config_dict,
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                failed_with_flex_tier=failed_with_flex_tier,
                api_key=api_key,
            )

        raise ValueError(f"Unknown provider: {provider}")

    except BaseException as e:
        if not _is_prompt_too_long_error(e):
            raise

        # Don't crash the whole bench on one long datapoint.
        LOG.warning(
            "Judge prompt too long; returning empty response. Error: %s",
            e,
        )
        return "", 0, 0, 0, failed_with_flex_tier


def run_in_parallel(
    *,
    user_messages: List[str],
    process_message: Callable[[str], str],
    max_workers: int,
) -> List[str]:
    """Run `process_message` over messages in parallel with a progress bar."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_message, user_messages)
        return list(tqdm.tqdm(results, total=len(user_messages)))
