import logging
from pathlib import Path
from typing import Any

from agent_lens.eval.common.llm_judge_usage import LlmJudgeUsageTracker
from agent_lens.eval.common.paths import sanitize_path_component
from agent_lens.eval.common.run_naming import run_task_name_from_run_info
from agent_lens.eval.data_framework.compute.dataset_builder import (
    dumps_to_dataset,
    get_run_info,
)
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.integrations.bench_constants import (
    EVAL_REPORT_ARTIFACT_NAME,
)
from agent_lens.eval.integrations.tracking_projects import eval_project_name
from agent_lens.eval.integrations.tracking import (
    EvalFinishInfo,
    TrackingConfig,
    finish_eval_tracking,
    start_eval_tracking,
)
from agent_lens.eval.metrics.analytics.get_analytics import (
    get_basic_aggregates,
    get_tool_success_stats,
)
from agent_lens.eval.metrics.tag_to_metrics import AgentScenarioTags
from agent_lens.eval.common.best_effort import best_effort
from agent_lens.eval.common.logging_setup import suppress_httpx_warnings
from agent_lens.eval.common.yaml_io import load_yaml_mapping
from agent_lens.eval.reporting.eval_markdown import generate_run_markdown
from agent_lens.eval.reporting.eval_tldr import EvalTldr
from agent_lens.eval.reporting.markdown_generation import generate_markdowns
from agent_lens.eval.reporting.run_dump import dump_data

LOG = logging.getLogger(__name__)

suppress_httpx_warnings()


def run_bench(
    *,
    config_path: str,
    idea_dumps_path: str,
    dump_dir: str,
    tracking_config: TrackingConfig,
    api_key: str,
) -> None:
    """Run benchmark evaluation pipeline (dataset -> per-tag reports -> dump outputs).

    Behavior must stay stable because it defines the on-disk report schema.
    """

    config = load_yaml_mapping(config_path, strict=True)

    run_info = get_run_info(idea_dumps_path)
    run_name = run_task_name_from_run_info(run_info)

    tracking_handle = start_eval_tracking(
        tracking_config=tracking_config,
        project_name=eval_project_name(tracking_config=tracking_config),
        run_name=run_name,
    )

    dataset = dumps_to_dataset(idea_dumps_path)

    for language, language_data in dataset.items():
        reports: dict[str, Any] = {}

        for tag_name in AgentScenarioTags.get_tags():
            if not config["eval"]["split_report_with_tag"][tag_name]:
                continue

            tag_data = {
                k: v
                for k, v in language_data.items()
                if tag_name in v[FieldNames.AGENT_BENCH_TAGS]
            }
            if len(tag_data) == 0:
                LOG.warning(
                    "No data points for %s language for tag %s, skipping.",
                    language,
                    tag_name,
                )
                continue

            with LlmJudgeUsageTracker.capture_usage_delta() as usage_capture:
                reports[tag_name] = get_basic_aggregates(
                    tag_data, tag_name
                ) | get_tool_success_stats(tag_data)

                for metrics_cls in AgentScenarioTags.TagToMetrics[tag_name]:
                    metrics = metrics_cls(config, api_key=api_key)
                    metrics.select_points(tag_data)
                    metrics.compute_single_run_reviews()
                    reports[tag_name].update(metrics.single_run_aggregate())

                reports[tag_name]["TLDR"] = EvalTldr(config, api_key=api_key).get_tldr(
                    reports[tag_name]
                )

            judge_usage = usage_capture.usage

            reports[tag_name].update(
                {
                    "judge": config["judge_model"],
                    "evaluation price": judge_usage.price_usd(
                        judge=config["judge_model"],
                        flex_service_tier=config["prefer_flex_service_tier"],
                    ),
                    "path to IDEA dumps": idea_dumps_path,
                }
            )

        dump_data(run_info, language_data, reports, dump_dir, language, config)

        run_dir = Path(dump_dir) / sanitize_path_component(run_name) / language
        best_effort(
            lambda: generate_markdowns(
                target_dir=run_dir,
                generate_for_dir=generate_run_markdown,
            ),
            what=f"run markdown generation for {run_name}/{language}",
        )

    finish_eval_tracking(
        handle=tracking_handle,
        dump_dir=dump_dir,
        artifact_name=EVAL_REPORT_ARTIFACT_NAME,
        finish_info=EvalFinishInfo(comment=None),
        tracking_config=tracking_config,
    )
