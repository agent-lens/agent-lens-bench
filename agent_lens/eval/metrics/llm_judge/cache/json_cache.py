import json
import logging
import os
from typing import Dict

from agent_lens.eval.metrics.llm_judge.cache.file_lock import (
    lock_exclusive,
    lock_shared,
    unlock,
)

LOG = logging.getLogger(__name__)


def load_json_cache(cache_path: str) -> Dict:
    if not os.path.exists(cache_path):
        return {}

    with open(cache_path, "r", encoding="utf-8") as f:
        lock_shared(f)
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            LOG.error("Failed to load cache from %s: %s", cache_path, e)
            return {}
        finally:
            unlock(f)


def save_json_cache(*, cache_path: str, cache: Dict) -> None:
    LOG.debug("Saving cache to %s...", cache_path)
    try:
        cache_dir = os.path.dirname(cache_path)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        # Load existing cache, merge with current, then save.
        with open(cache_path, "a+", encoding="utf-8") as f:
            lock_exclusive(f)
            try:
                f.seek(0)
                existing_cache = {}
                if f.read().strip():
                    f.seek(0)
                    existing_cache = json.load(f)

                merged_cache = {**existing_cache, **cache}

                f.seek(0)
                f.truncate()
                json.dump(merged_cache, f, indent=2, ensure_ascii=False)
            finally:
                unlock(f)
    except (OSError, json.JSONDecodeError) as e:
        LOG.warning("Failed to save cache to %s: %s", cache_path, e)
