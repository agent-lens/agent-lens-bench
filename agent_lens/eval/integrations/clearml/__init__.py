"""ClearML integration boundary.

This package is the only place in agent_bench allowed to import the `clearml` SDK.
All imports of the SDK itself are done lazily via `import_clearml_sdk()`.
"""

from agent_lens.eval.integrations.clearml.facade import (
    download_artifact,
    find_anchor_run_by_schedule,
    finish_eval_tracking,
    finish_sbs_tracking,
    publish_merged_folds,
    start_eval_tracking,
    start_sbs_tracking,
)

__all__ = [
    "download_artifact",
    "find_anchor_run_by_schedule",
    "finish_eval_tracking",
    "finish_sbs_tracking",
    "publish_merged_folds",
    "start_eval_tracking",
    "start_sbs_tracking",
]
