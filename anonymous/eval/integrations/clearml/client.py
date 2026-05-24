import logging
import os
from functools import lru_cache
from typing import Any, Protocol

LOG = logging.getLogger(__name__)


class ClearMLModule(Protocol):
    """Minimal surface of the `clearml` module we rely on.

    This protocol is for type-checking only and does not import the ClearML SDK at runtime.
    """

    Task: Any
    TaskTypes: Any


_MISSING_SDK_MESSAGE = (
    "ClearML tracking backend is selected (tracking_backend: clearml), "
    "but the ClearML SDK is not installed.\n\n"
    "Install it:\n"
    "  pip install clearml"
)

_MISSING_CONFIG_MESSAGE = (
    "ClearML tracking backend is selected (tracking_backend: clearml), "
    "but ClearML is not configured on this machine.\n\n"
    "Initialize ClearML:\n"
    "  clearml-init"
)


_ENV_CLEARML_LOG_LEVEL = "CLEARML_LOG_LEVEL"
_ENV_CLEARML_SUPPRESS_UPDATE_MESSAGE = "CLEARML_SUPPRESS_UPDATE_MESSAGE"


def configure_clearml_runtime_env() -> None:
    """Set default ClearML env vars to reduce console noise.

    Separated from SDK import to avoid side effects during import.
    """

    os.environ.setdefault(_ENV_CLEARML_LOG_LEVEL, "40")
    os.environ.setdefault(_ENV_CLEARML_SUPPRESS_UPDATE_MESSAGE, "1")


@lru_cache(maxsize=1)
def import_clearml_sdk() -> ClearMLModule:
    """Import and validate the ClearML SDK.

    This is strict by design: if the backend is selected, ClearML must be usable.
    """

    try:
        import clearml  # type: ignore
    except ImportError as e:
        raise RuntimeError(_MISSING_SDK_MESSAGE) from e

    # Trigger config/env loading early to fail fast with a friendly message.
    try:
        from clearml.backend_api.session.defs import MissingConfigError  # type: ignore

        try:
            from clearml.backend_api.session import Session  # type: ignore

            Session()
        except MissingConfigError as e:
            raise RuntimeError(_MISSING_CONFIG_MESSAGE) from e
    except ImportError:
        # If the SDK structure changes, we still keep the strict import.
        LOG.debug(
            "ClearML SDK does not expose MissingConfigError in the expected place; skipping config check."
        )

    return clearml  # type: ignore[return-value]
