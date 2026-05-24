import logging
from typing import Literal, TypedDict, cast

from agent_lens.eval.comparison.compute.models import AlertInfo
from agent_lens.eval.integrations.sbs_schedule import SbsRunMode
from agent_lens.eval.integrations.tracking import (
    TrackingConfig,
    TrackingHandle,
    tracking_run_url,
)
from agent_lens.eval.integrations.github import get_current_github_action_link

LOG = logging.getLogger(__name__)

BackendName = Literal["none", "telegram"]

_BACKEND_TELEGRAM: Literal["telegram"] = "telegram"
_BACKEND_NONE: Literal["none"] = "none"

_ALLOWED_BACKENDS: set[BackendName] = {_BACKEND_TELEGRAM, _BACKEND_NONE}
_DEFAULT_BACKEND: BackendName = _BACKEND_NONE


class AlertingConfigDict(TypedDict, total=False):
    alerting_backend: str


def resolve_alerting_backend(*, tracking_config: TrackingConfig) -> BackendName:
    """Resolve selected alerting backend from the provided config dict."""

    backend_raw = (tracking_config or {}).get("alerting_backend")
    if backend_raw is None or str(backend_raw).strip() == "":
        backend_raw = _DEFAULT_BACKEND

    backend = str(backend_raw).strip().lower()
    if backend not in _ALLOWED_BACKENDS:
        raise ValueError(
            f"Unknown alerting backend: {backend!r}. Allowed: {sorted(_ALLOWED_BACKENDS)}"
        )

    return cast(BackendName, backend)


def send_alerts(
    alerts: AlertInfo,
    tldr: str,
    bench_tag_name: str,
    language: str,
    sbs_name: str,
    tracking_handle: TrackingHandle,
    schedule: SbsRunMode,
    tracking_config: TrackingConfig,
    retries: int = 1,
) -> None:
    """Send regression alerts via a configured backend.

    Manual runs are ignored.
    """

    if not schedule.is_scheduled:
        return

    backend = resolve_alerting_backend(tracking_config=tracking_config)
    if backend == _BACKEND_NONE:
        return

    if backend == _BACKEND_TELEGRAM:
        from agent_lens.eval.integrations.telegram import (
            send_alerts as telegram_send,
        )

        tracking_url = tracking_run_url(
            tracking_config=tracking_config, handle=tracking_handle
        )
        github_action_run_url = get_current_github_action_link(tracking_config)
        telegram_send(
            alerts,
            tldr,
            bench_tag_name,
            language,
            sbs_name,
            tracking_url,
            github_action_run_url,
            retries,
        )
        return

    LOG.warning("Alerting backend %r is not implemented.", backend)
