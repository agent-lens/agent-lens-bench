import logging
from pathlib import Path
from typing import Callable

from anonymous.eval.common.best_effort import best_effort

LOG = logging.getLogger(__name__)


def generate_markdowns(
    *,
    target_dir: Path,
    generate_for_dir: Callable[[Path], int],
) -> None:
    def _generate() -> int:
        return int(generate_for_dir(target_dir))

    written = best_effort(
        _generate,
        what=f"markdown generation for {target_dir}",
    )
    if written is None:
        return

    if written > 0:
        LOG.info("Markdown report generated in: %s", target_dir)
    elif written < 0:
        LOG.info("No Markdown inputs for %s, skipping", target_dir)
    else:
        LOG.error("Markdown generation produced 0 files for %s", target_dir)


def generate_markdowns_in_subdirs(
    *,
    parent_dir: Path,
    generate_for_dir: Callable[[Path], int],
) -> None:
    if not parent_dir.is_dir():
        return

    for subdir in parent_dir.iterdir():
        if subdir.is_dir():
            generate_markdowns(target_dir=subdir, generate_for_dir=generate_for_dir)
