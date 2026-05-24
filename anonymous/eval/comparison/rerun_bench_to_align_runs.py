import copy
import logging
from typing import Dict, Set, Type

from anonymous.eval.comparison.compute.models import RunData
from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.metrics.analytics.get_analytics import (
    get_basic_aggregates,
    get_tool_success_stats,
)
from anonymous.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from anonymous.eval.metrics.tag_to_metrics import AgentScenarioTags

LOG = logging.getLogger(__name__)


def _collect_llm_metrics() -> Set[Type[LlmMetric]]:
    metrics: Set[Type[LlmMetric]] = set()
    for lst in AgentScenarioTags.TagToMetrics.values():
        for m in lst:
            metrics.add(m)
    return metrics


def _recompute_report_only(
    dataset: Dict,
    report: Dict,
    config: Dict,
    api_key: str,
    bench_tag_name: str,
) -> Dict:
    new_report = copy.deepcopy(report)

    # Basic analytics (same as in run_agent_bench)
    new_report.update(
        get_basic_aggregates(dataset, bench_tag_name) | get_tool_success_stats(dataset)
    )

    # Judge metrics aggregation: reuse existing per-point metrics, only re-run summaries
    for metrics_cls in _collect_llm_metrics():
        metrics_name = metrics_cls.get_name()
        points_with_metric = {k: v for k, v in dataset.items() if metrics_name in v}
        if not points_with_metric:
            continue

        metrics = metrics_cls(config, api_key=api_key)
        # do NOT recompute per-point, just feed existing data
        metrics.select_points(points_with_metric)
        agg = metrics.single_run_aggregate()
        new_report.update(agg)

    # Update common fields
    new_report[FieldNames.NUM_CHATS] = len(dataset)
    return new_report


def rerun_aggregation_to_align(
    *, config: Dict, run_data: RunData, api_key: str, bench_tag_name: str
) -> RunData:
    keys1 = set(run_data.dataset1.keys())
    keys2 = set(run_data.dataset2.keys())

    missing_in_1 = sorted(list(keys2 - keys1))
    missing_in_2 = sorted(list(keys1 - keys2))
    LOG.info("Missing in dataset1: %s", missing_in_1)
    LOG.info("Missing in dataset2: %s", missing_in_2)
    common_keys = sorted(keys1.intersection(keys2))

    # Trim datasets to common key set
    run_data.dataset1 = {k: run_data.dataset1[k] for k in common_keys}
    run_data.dataset2 = {k: run_data.dataset2[k] for k in common_keys}

    # Recompute reports for trimmed datasets (aggregation only)
    run_data.report1 = _recompute_report_only(
        run_data.dataset1,
        run_data.report1,
        config,
        api_key=api_key,
        bench_tag_name=bench_tag_name,
    )
    run_data.report2 = _recompute_report_only(
        run_data.dataset2,
        run_data.report2,
        config,
        api_key=api_key,
        bench_tag_name=bench_tag_name,
    )

    LOG.info("Alignment complete: datasets trimmed and reports re-aggregated.")
    return run_data
