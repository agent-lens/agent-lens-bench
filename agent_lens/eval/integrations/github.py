import os
from typing import Optional

from agent_lens.eval.integrations.tracking import TrackingConfig

_GITHUB_RUN_ID_ENV = "GITHUB_RUN_ID"


def get_current_github_action_link(tracking_config: TrackingConfig) -> Optional[str]:
    github_run_id = os.getenv(_GITHUB_RUN_ID_ENV)
    gh_action_run_url = tracking_config.get("github_action_run_url")
    if github_run_id is not None and gh_action_run_url is not None:
        return gh_action_run_url + github_run_id
    return None
