import logging
from pathlib import Path


LOG = logging.getLogger(__name__)

MERGED_SUMMARY_JSON_NAME = "summary_merged.json"


def list_summary_files(base_dir: Path) -> list[Path]:
    if base_dir.is_file():
        base_dir = base_dir.parent
    # Keep semantics stable but deterministic: recursive discovery + sorted paths.
    return sorted(base_dir.rglob("summary*.json"))


def pick_summary_file(base_dir: Path) -> Path:
    """Pick merged summary if present, otherwise the largest summary JSON."""
    candidates = list_summary_files(base_dir)
    if not candidates:
        raise FileNotFoundError(f"Can't find a valid summary file under: {base_dir}")

    merged = [p for p in candidates if p.name == MERGED_SUMMARY_JSON_NAME]
    if merged:
        chosen = merged[0]
        LOG.info("Picked merged summary file: %s", chosen)
        return chosen

    def _key(p: Path) -> tuple[int, str]:
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            size = -1
        return size, p.as_posix()

    chosen = max(candidates, key=_key)
    LOG.info("Picked summary file: %s", chosen)
    return chosen
