import argparse
import os

from anonymous.eval.common.yaml_io import load_yaml_mapping
from anonymous.eval.metrics.llm_judge.providers.registry import (
    PROVIDER_OPENAI_COMPATIBLE,
    get_judge_provider,
)

def str2bool(v):
    """Convert GitHub actions style booleans (`true/false`) to python bool values."""
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    if v.lower() in ("no", "false", "f", "n", "0"):
        return False
    raise argparse.ArgumentTypeError("Boolean value expected.")


def resolve_llm_api_key(*, api_key_arg: str, config_path: str) -> str:
    """Resolve the judge API key (env LLM_API_KEY mirrors --api_key).

    An empty key is allowed only for `judge_provider == openai_compatible`,
    because such backends frequently don't require auth.
    """
    api_key = str(api_key_arg or "").strip()
    if api_key != "":
        os.environ["LLM_API_KEY"] = api_key

    api_key = api_key or str(os.getenv("LLM_API_KEY") or "").strip()
    if api_key == "":
        config = load_yaml_mapping(config_path, strict=True)
        if get_judge_provider(config) != PROVIDER_OPENAI_COMPATIBLE:
            raise ValueError(
                "Missing judge API key: pass --api_key or set env LLM_API_KEY "
                "(empty key is allowed only when judge_provider == "
                f"{PROVIDER_OPENAI_COMPATIBLE!r})."
            )

    return api_key
