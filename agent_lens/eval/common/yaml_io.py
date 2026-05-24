from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(
    path: str | Path | None, *, strict: bool = False
) -> dict[str, Any]:
    """Load a YAML mapping from `path`.

    Semantics:
    - If `path` is blank/missing and strict=False: returns {}.
    - If `path` is blank/missing and strict=True: raises.
    - If YAML is empty: returns {}.
    - If YAML root is not a mapping: raises ValueError.

    This keeps pipeline + tracking config loading consistent.
    """

    if path is None or str(path).strip() == "":
        if strict:
            raise ValueError("YAML config path is blank")
        return {}

    p = Path(path)
    if not p.is_file():
        if strict:
            raise FileNotFoundError(f"YAML config file does not exist: {p}")
        return {}

    with p.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML config must be a mapping, got: {type(loaded).__name__}")

    return loaded
