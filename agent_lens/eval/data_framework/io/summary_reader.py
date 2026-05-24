from pathlib import Path
from typing import Mapping

from agent_lens.eval.common.json_io import read_json
from agent_lens.eval.data_framework.io.summary_finder import pick_summary_file
from agent_lens.eval.data_framework.models import SummaryFile


def read_summary_file(base_dir: Path) -> SummaryFile:
    """Load the chosen summary JSON under `base_dir` and parse it into a `SummaryFile`."""

    summary_path = pick_summary_file(base_dir)
    data = read_json(summary_path)
    if not isinstance(data, Mapping):
        raise ValueError(f"Summary file root is not an object: {summary_path}")

    # Note: `SummaryFile.from_dict` is defensive; it normalizes missing/invalid fields.
    return SummaryFile.from_dict(data)
