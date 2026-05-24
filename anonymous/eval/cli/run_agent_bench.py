import argparse
import logging
from typing import cast

from anonymous.eval.common.cli import resolve_llm_api_key, str2bool
from anonymous.eval.common.yaml_io import load_yaml_mapping
from anonymous.eval.common.logging_setup import suppress_httpx_warnings
from anonymous.eval.integrations.tracking import ClearmlTrackingConfig, TrackingConfig
from anonymous.eval.pipelines.run_bench_pipeline import run_bench

suppress_httpx_warnings()


def parse_cmd_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config_path",
        default="anonymous/eval/configs/agent_bench_config.yaml",
        help="Path to config file for the python benchmark",
        type=str,
    )
    parser.add_argument(
        "-k",
        "--api_key",
        help="API key for an LLM chosen as a judge model (or set env LLM_API_KEY; may be empty only when judge_provider == openai_compatible)",
        required=False,
        default="",
        type=str,
    )
    parser.add_argument(
        "--tracking_config_path",
        default="anonymous/eval/configs/tracking_config.yaml",
        help="Path to tracking config",
        required=False,
        type=str,
    )
    parser.add_argument(
        "--idea_logs_path",
        help="Input: path to IDEA dumps folder",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--dump_dir",
        help="Output: folder where benchmark results will be written",
        type=str,
        required=False,
        default="./benchmark_runs",
    )
    parser.add_argument(
        "--disable_tracking",
        type=str2bool,
        help="Force disable tracking, ignoring tracking config",
        required=False,
        default=False,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_cmd_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.disable_tracking:
        tracking_config = TrackingConfig(
            tracking_backend="none",
            alerting_backend="none",
            clearml=ClearmlTrackingConfig(
                eval_project_name="",
                sbs_project_name="",
                task_url_template="",
            ),
        )
    else:
        tracking_config: TrackingConfig = cast(
            TrackingConfig,
            load_yaml_mapping(args.tracking_config_path, strict=True),
        )

    api_key = resolve_llm_api_key(
        api_key_arg=args.api_key, config_path=args.config_path
    )

    run_bench(
        config_path=args.config_path,
        idea_dumps_path=args.idea_logs_path,
        dump_dir=args.dump_dir,
        tracking_config=tracking_config,
        api_key=api_key,
    )


if __name__ == "__main__":
    main()
