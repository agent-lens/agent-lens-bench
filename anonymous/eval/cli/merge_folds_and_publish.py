import argparse
import logging
from typing import cast

from anonymous.eval.common.cli import str2bool
from anonymous.eval.common.yaml_io import load_yaml_mapping
from anonymous.eval.integrations.sbs_schedule import SbsRunMode
from anonymous.eval.integrations.tracking import ClearmlTrackingConfig, TrackingConfig
from anonymous.eval.pipelines.merge_folds_pipeline import (
    merge_folds_and_publish,
)

LOG = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input_folder",
        required=True,
        help="Path to folder with benchmark folds",
        type=str,
    )
    parser.add_argument(
        "-o",
        "--output_folder",
        required=True,
        help="Path to output folder",
        type=str,
    )
    parser.add_argument(
        "--tracking_config_path",
        default="anonymous/eval/configs/tracking_config.yaml",
        help="Path to tracking config (tracking backend + ClearML URL template)",
        required=False,
        type=str,
    )
    parser.add_argument(
        "--is_nightly_mode",
        type=str2bool,
        help="Nightly regression test run or not",
        required=False,
        default=False,
    )
    parser.add_argument(
        "--is_weekly_mode",
        type=str2bool,
        help="Weekly regression test run or not",
        required=False,
        default=False,
    )
    parser.add_argument(
        "--disable_tracking",
        type=str2bool,
        help="Force disable tracking, ignoring tracking config",
        required=False,
        default=False,
    )

    args = parser.parse_args()


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

    schedule = SbsRunMode.from_flags(
        is_nightly_mode=args.is_nightly_mode,
        is_weekly_mode=args.is_weekly_mode,
    )

    merged_name = merge_folds_and_publish(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        schedule=schedule,
        tracking_config=tracking_config,
    )

    LOG.info("Merged run name (for CI): %s", merged_name)
    print(merged_name)  # don't remove, it's used by CI


if __name__ == "__main__":
    main()
