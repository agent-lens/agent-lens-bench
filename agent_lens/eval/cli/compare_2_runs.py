import argparse
import logging
from argparse import ArgumentParser
from collections.abc import Callable
from typing import cast

from agent_lens.eval.common.cli import resolve_llm_api_key, str2bool
from agent_lens.eval.common.yaml_io import load_yaml_mapping
from agent_lens.eval.common.logging_setup import suppress_httpx_warnings
from agent_lens.eval.integrations.tracking import TrackingConfig
from agent_lens.eval.pipelines.sbs_compare_pipeline import compare_2_runs

suppress_httpx_warnings()


def parse_cmd_args(
    extra_params: Callable[[ArgumentParser], None] = lambda _: None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config_path",
        default="agent_lens/eval/configs/agent_bench_config.yaml",
        required=False,
    )
    parser.add_argument(
        "-k",
        "--api_key",
        help="API key for an LLM chosen as a judge (or set env LLM_API_KEY; may be empty only when judge_provider == openai_compatible)",
        required=False,
        default="",
    )
    parser.add_argument(
        "--tracking_config_path",
        default="agent_lens/eval/configs/tracking_config.yaml",
        help="Path to tracking config (tracking backend + ClearML URL template)",
        required=False,
    )
    parser.add_argument(
        "--data_dir",
        help="Input: folder with eval runs (benchmark outputs)",
        required=False,
        default="./benchmark_runs",
    )
    parser.add_argument("--name", help="Side-by-side comparison name", required=True)
    parser.add_argument(
        "--dump_dir",
        help="Output folder for the comparison results",
        required=False,
        default="./sbs_comparisons",
    )
    parser.add_argument(
        "--is_nightly_mode",
        type=str2bool,
        help="Nightly regression test run or not",
        required=False,
        default=False,
    )
    parser.add_argument(
        "--run1_name", type=str, help="Anchor eval run name", required=True
    )
    parser.add_argument(
        "--run2_name", type=str, help="Current eval run name", required=True
    )
    extra_params(parser)
    args = parser.parse_args()
    return args


def main():
    args = parse_cmd_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tracking_config: TrackingConfig = cast(
        TrackingConfig,
        load_yaml_mapping(args.tracking_config_path, strict=True),
    )

    api_key = resolve_llm_api_key(
        api_key_arg=args.api_key, config_path=args.config_path
    )

    compare_2_runs(
        config_path=args.config_path,
        data_dir=args.data_dir,
        name=args.name,
        dump_dir=args.dump_dir,
        run1_name=args.run1_name,
        run2_name=args.run2_name,
        tracking_config=tracking_config,
        api_key=api_key,
    )


if __name__ == "__main__":
    main()
