"""HTTP helpers used by optional integrations."""

import time
from typing import Any, Optional

import requests


def post_json_with_retries(
    *,
    url: str,
    payload: dict[str, Any],
    retries: int,
    timeout_s: float,
    logger,
    backoff_s: float = 0.0,
) -> Optional[requests.Response]:
    """POST JSON with best-effort retries.

    `retries` follows the existing semantics in agent_bench integrations:
    total attempts = max(1, retries + 1).
    """

    total_attempts = max(1, retries + 1)

    last_response: Optional[requests.Response] = None
    for attempt in range(1, total_attempts + 1):
        try:
            response = requests.post(url, json=payload, timeout=timeout_s)
            last_response = response
            if response.ok:
                return response
            logger.warning(
                "HTTP POST failed (attempt %d/%d, status=%s): %s",
                attempt,
                total_attempts,
                getattr(response, "status_code", ""),
                getattr(response, "text", ""),
            )
        except Exception as e:  # noqa: BLE001 - best-effort integrations
            logger.warning(
                "HTTP POST raised exception (attempt %d/%d): %r",
                attempt,
                total_attempts,
                e,
            )

        if backoff_s > 0 and attempt < total_attempts:
            time.sleep(backoff_s)

    return last_response
