import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from anonymous.eval.comparison.compute.comparisons import (
    compare_cache_hit,
    compare_formal_verification,
    compare_gen_tokens,
    compare_judge_metrics_trajectory_based,
    compare_price,
    compare_setups,
    compare_termination_reasons,
    compare_test_metrics,
    compare_time,
    compare_gen_tokens_to_seconds_ratio,
    compare_tool_call_count,
    compare_tool_calls_in_parallel,
    compare_tool_success,
)
from anonymous.eval.comparison.compute.models import (
    AlertInfo,
    Comparison,
    RunData,
)
from anonymous.eval.comparison.io.comparison_dump import dump_comparison
from anonymous.eval.comparison.is_data_equal import DataManagerForTag
from anonymous.eval.comparison.rerun_bench_to_align_runs import (
    rerun_aggregation_to_align,
)
from anonymous.eval.reporting.comparison_tldr import ComparisonTldr
from anonymous.eval.common.llm_judge_usage import LlmJudgeUsageTracker
from anonymous.eval.common.paths import sanitize_path_component
from anonymous.eval.common.time import get_nice_time
from anonymous.eval.integrations.bench_constants import SBS_REPORT_ARTIFACT_NAME
from anonymous.eval.metrics.llm_judge.common.review_style_user import (
    get_review_timezone,
)
from anonymous.eval.metrics.tag_names import TagNames
from anonymous.eval.integrations.alerting import send_alerts
from anonymous.eval.integrations.sbs_schedule import SbsRunMode
from anonymous.eval.integrations.tracking_projects import sbs_project_name
from anonymous.eval.integrations.tracking import (
    SbsFinishInfo,
    TrackingConfig,
    TrackingHandle,
    finish_sbs_tracking,
    start_sbs_tracking,
)
from anonymous.eval.common.best_effort import best_effort
from anonymous.eval.common.logging_setup import suppress_httpx_warnings
from anonymous.eval.common.yaml_io import load_yaml_mapping
from anonymous.eval.reporting import sbs_markdown
from anonymous.eval.reporting.markdown_generation import (
    generate_markdowns_in_subdirs,
)

LOG = logging.getLogger(__name__)

suppress_httpx_warnings()


@dataclass(frozen=True)
class ComparisonBundle:
    comparisons: list[Comparison]
    tldr: str
    metadata: Dict[str, Any]
    alerts: AlertInfo
    judge_summary_dialogues: Dict[str, str]
    judge_comparison_dialogues: Optional[Dict[str, Dict[str, str]]]


def ensure_runs_aligned_for_comparison(
    *,
    run_data: RunData,
    data_conformity_report: Dict[str, Any],
    config: Dict,
    bench_tag_name: str,
    api_key: str,
) -> RunData:
    if not data_conformity_report["datasets_compatible"]:
        errors_joined = "\n   ".join(data_conformity_report["errors"])
        LOG.warning(
            "\nDatasets are not compatible for %s tag. Errors:\n   %s.",
            bench_tag_name,
            errors_joined,
        )
        if data_conformity_report["should_align"]:
            LOG.info(
                "Rerunning aggregation for %s tag to align runs...\n", bench_tag_name
            )
            run_data = rerun_aggregation_to_align(
                config=config,
                run_data=run_data,
                api_key=api_key,
                bench_tag_name=bench_tag_name,
            )
            LOG.info("\nStarting comparison for tag %s...", bench_tag_name)

    return run_data


def _compute_bundle(
    *,
    run_data: RunData,
    config: Dict,
    bench_tag_name: str,
    data_conformity_report: Dict[str, Any],
    api_key: str,
) -> ComparisonBundle:
    with LlmJudgeUsageTracker.capture_usage_delta() as usage_capture:
        (
            judge_comparisons,
            judge_summary_dialogues,
            judge_comparison_dialogues,
        ) = compare_judge_metrics_trajectory_based(
            run_data, config, bench_tag_name, api_key
        )

    judge_usage = usage_capture.usage

    tool_comparisons = compare_tool_success(run_data)
    test_metric_comparisons = (
        compare_test_metrics(run_data) if bench_tag_name == TagNames.testing else []
    )
    termination_reasons_comparison = compare_termination_reasons(run_data)
    setup_comparison = compare_setups(run_data, data_conformity_report)
    price_comparison = compare_price(run_data)
    time_comparison = compare_time(run_data)
    gen_tokens_to_seconds_ratio_comparison = compare_gen_tokens_to_seconds_ratio(
        run_data
    )
    tool_call_count_comparison = compare_tool_call_count(run_data)
    gen_tokens_comparison = compare_gen_tokens(run_data)
    cache_hit_comparison = compare_cache_hit(run_data)
    formal_verification_comparison = compare_formal_verification(run_data)
    parallel_calls_comparison = compare_tool_calls_in_parallel(run_data)

    # Preserve output ordering exactly (stable schema for dumping + markdown rendering).
    comparisons = (
        judge_comparisons
        + tool_comparisons
        + test_metric_comparisons
        + [
            formal_verification_comparison,
            termination_reasons_comparison,
            price_comparison,
            time_comparison,
            gen_tokens_to_seconds_ratio_comparison,
            tool_call_count_comparison,
            gen_tokens_comparison,
            cache_hit_comparison,
            parallel_calls_comparison,
            setup_comparison,
        ]
    )

    metadata = {
        "name": "metadata",
        "judge": {
            "model": config["judge_model"],
            "prompt_tokens": judge_usage.prompt_tokens,
            "cached_tokens": judge_usage.cached_tokens,
            "completion_tokens": judge_usage.completion_tokens,
            "api_calls": judge_usage.api_calls,
            "total_price_usd": judge_usage.price_usd(
                judge=config["judge_model"],
                flex_service_tier=config["prefer_flex_service_tier"],
            ),
        },
        "run1": {
            "run_name": run_data.report1["run name"],
            "model_info": run_data.report1["model_info"],
            "plugin_hash": run_data.report1["plugin_hash"],
        },
        "run2": {
            "run_name": run_data.report2["run name"],
            "model_info": run_data.report2["model_info"],
            "plugin_hash": run_data.report2["plugin_hash"],
        },
    }

    alerts = AlertInfo(
        [c.get_text_presentation(minimize=True) for c in comparisons if c.warning_flag],
        [c.get_text_presentation(minimize=False) for c in comparisons if c.alert_flag],
    )

    tldr = ComparisonTldr(config, api_key=api_key).get_tldr(comparisons)

    return ComparisonBundle(
        comparisons=comparisons,
        tldr=tldr,
        metadata=metadata,
        alerts=alerts,
        judge_summary_dialogues=judge_summary_dialogues,
        judge_comparison_dialogues=judge_comparison_dialogues,
    )


def compare_2_runs(
    *,
    config_path: str,
    data_dir: str,
    name: str,
    dump_dir: str,
    is_nightly_mode: bool = False,
    is_weekly_mode: bool = False,
    run1_name: str,
    run2_name: str,
    tracking_config: TrackingConfig,
    api_key: str,
) -> None:
    """Side-by-side comparison pipeline (reports + datasets -> comparisons -> dump + MD + alerts)."""

    config = dict(load_yaml_mapping(config_path, strict=True))

    autogen_name = f"run1_{run1_name}_VS_run2_{run2_name}"
    sbs_name_raw = name if not (len(name) == 0 or name.isspace()) else autogen_name
    sbs_name = f"{sbs_name_raw}_{get_nice_time(get_review_timezone(config))}"

    config["name"] = sbs_name
    config["data_dir"] = data_dir
    config["dump_dir"] = dump_dir
    config["run1_name"] = run1_name
    config["run2_name"] = run2_name

    schedule = SbsRunMode.from_flags(
        is_nightly_mode=is_nightly_mode,
        is_weekly_mode=is_weekly_mode,
    )

    tracking_handle = start_sbs_tracking(
        tracking_config=tracking_config,
        project_name=sbs_project_name(tracking_config=tracking_config),
        task_name=sbs_name,
        schedule=schedule,
    )

    for tag in config["sbs"]["tags_to_compare"]:
        compare_2_runs_for_tag(
            config=config,
            bench_tag_name=tag,
            schedule=schedule,
            tracking_handle=tracking_handle,
            tracking_config=tracking_config,
            api_key=api_key,
        )

    comparison_dir = Path(dump_dir) / sanitize_path_component(sbs_name)
    best_effort(
        lambda: generate_markdowns_in_subdirs(
            parent_dir=comparison_dir,
            generate_for_dir=sbs_markdown.generate_comparison_markdown,
        ),
        what=f"sbs markdown generation for {sbs_name}",
    )

    finish_sbs_tracking(
        handle=tracking_handle,
        dump_dir=dump_dir,
        artifact_name=SBS_REPORT_ARTIFACT_NAME,
        tracking_config=tracking_config,
        finish_info=SbsFinishInfo(comment=autogen_name, task_name=sbs_name),
    )


def compare_2_runs_for_tag(
    *,
    config: Dict,
    bench_tag_name: str,
    schedule: SbsRunMode,
    tracking_handle: TrackingHandle,
    tracking_config: TrackingConfig,
    api_key: str,
) -> None:
    data_manager = DataManagerForTag(config, bench_tag_name)
    for language, run_data in data_manager.get_run_data_for_tag().items():
        compare_2_runs_for_lang(
            run_data=run_data,
            language=language,
            data_manager=data_manager,
            config=config,
            bench_tag_name=bench_tag_name,
            schedule=schedule,
            tracking_handle=tracking_handle,
            tracking_config=tracking_config,
            api_key=api_key,
        )


def compare_2_runs_for_lang(
    *,
    run_data: RunData,
    language: str,
    data_manager: DataManagerForTag,
    config: Dict,
    bench_tag_name: str,
    schedule: SbsRunMode,
    tracking_handle: TrackingHandle,
    tracking_config: TrackingConfig,
    api_key: str,
) -> None:
    data_conformity_report = data_manager.do_runs_conform(run_data, language)
    run_data = ensure_runs_aligned_for_comparison(
        run_data=run_data,
        data_conformity_report=data_conformity_report,
        config=config,
        bench_tag_name=bench_tag_name,
        api_key=api_key,
    )

    bundle = _compute_bundle(
        run_data=run_data,
        config=config,
        bench_tag_name=bench_tag_name,
        data_conformity_report=data_conformity_report,
        api_key=api_key,
    )

    send_alerts(
        bundle.alerts,
        bundle.tldr,
        bench_tag_name,
        language,
        config["name"],
        tracking_handle,
        schedule=schedule,
        tracking_config=tracking_config,
    )

    dump_comparison(
        bundle.comparisons,
        bundle.tldr,
        bundle.metadata,
        config,
        run_data,
        bench_tag_name,
        language,
        bundle.judge_summary_dialogues,
        judge_comparison_dialogues=bundle.judge_comparison_dialogues,
    )
