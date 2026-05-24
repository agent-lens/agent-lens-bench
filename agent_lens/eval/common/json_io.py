import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read JSON from `path`.

    Raises:
        FileNotFoundError: if the file does not exist.
        json.JSONDecodeError: if JSON is invalid.
    """

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Write JSON in the repo-wide stable format.

    Policy:
    - UTF-8 encoding
    - `ensure_ascii=False` (keep Unicode readable)
    - `indent=2` by default
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
