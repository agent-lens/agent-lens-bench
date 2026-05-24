import logging


def suppress_httpx_warnings() -> None:
    """Reduce noisy HTTP client logs from LLM SDKs.

    This is a process-wide logging configuration tweak, so it lives under `common/`.
    """

    logging.getLogger("httpx").setLevel(logging.WARNING)
