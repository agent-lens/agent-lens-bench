import logging
from argparse import ArgumentParser
from typing import cast

from anonymous.eval.common.cli import resolve_llm_api_key, str2bool

from anonymous.eval.integrations.clearml.clearml_download_helpers import (
    download_2_runs,
)
from anonymous.eval.cli.compare_2_runs import parse_cmd_args
from anonymous.eval.common.yaml_io import load_yaml_mapping
from anonymous.eval.integrations.sbs_schedule import SbsRunMode
from anonymous.eval.integrations.tracking import TrackingConfig
from anonymous.eval.pipelines.sbs_compare_pipeline import compare_2_runs

LOG = logging.getLogger(__name__)


def main():
    """It's used for sbs comparison GH workflow"""

    def define_extra_args(parser: ArgumentParser):
        parser.add_argument(
            "--is_weekly_mode",
            type=str2bool,
            help="Weekly regression test run or not",
            required=False,
            default=False,
        )

    args = parse_cmd_args(define_extra_args)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tracking_config: TrackingConfig = cast(
        TrackingConfig,
        load_yaml_mapping(args.tracking_config_path, strict=True),
    )

    api_key = resolve_llm_api_key(
        api_key_arg=args.api_key, config_path=args.config_path
    )
    schedule = SbsRunMode.from_flags(
        is_nightly_mode=args.is_nightly_mode,
        is_weekly_mode=args.is_weekly_mode,
    )

    run1_name, run2_name = download_2_runs(
        tracking_config=tracking_config,
        anchor_run_name=args.run1_name.strip(),
        current_run_name=args.run2_name.strip(),
        output_dir=args.data_dir,
        schedule=schedule,
    )

    LOG.info("Starting sbs comparison...")
    compare_2_runs(
        config_path=args.config_path,
        data_dir=args.data_dir,
        name=args.name,
        dump_dir=args.dump_dir,
        is_nightly_mode=args.is_nightly_mode,
        is_weekly_mode=args.is_weekly_mode,
        run1_name=run1_name,
        run2_name=run2_name,
        tracking_config=tracking_config,
        api_key=api_key,
    )


if __name__ == "__main__":
    main()
