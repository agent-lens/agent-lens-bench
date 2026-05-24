"""ClearML runtime entrypoint.

This module is responsible for the *runtime* preparation needed before calling
ClearML SDK APIs (env setup + lazy SDK import).

Keeping this logic in one place reduces boilerplate and keeps the integration
boundary easy to audit.
"""

from agent_lens.eval.integrations.clearml.client import (
    ClearMLModule,
    configure_clearml_runtime_env,
    import_clearml_sdk,
)


def get_clearml() -> ClearMLModule:
    """Return the ClearML SDK module (strict).

    This is safe to call multiple times: env setup is idempotent and the SDK
    import is cached.
    """

    configure_clearml_runtime_env()
    return import_clearml_sdk()
