import random
from typing import Dict, List, Optional, Tuple
from scipy.stats import fisher_exact

from anonymous.eval.common.statistics import (
    paired_permutation_test,
    safe_mannwhitneyu,
    safe_mean,
)
from anonymous.eval.comparison.compute.models import (
    JudgeMetricsComparison,
    PairwiseScalarComparison,
    RunData,
    ScalarMetricsComparison,
    SetupComparison,
    TerminationReasonsComparison,
    ToolMetricsComparison,
)
from anonymous.eval.comparison.compute.thresholds import (
    RatioPolicy,
    ratio_flags,
    safe_ratio,
)
from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.metrics.analytics.testing_metrics import (
    extract_test_metrics,
)
from anonymous.eval.metrics.llm_judge.interfaces.llm_metrics import (
    MAX_LLM_REVIEWED_POOL_SIZE,
)
from anonymous.eval.metrics.tag_to_metrics import AgentScenarioTags

TOOL_CALLS_COUNT_POLICY = RatioPolicy(
    warn_low=0.8, warn_high=1.3, alert_low=0.5, alert_high=2.0
)
GEN_TOKENS_POLICY = RatioPolicy(
    warn_low=0.8, warn_high=1.3, alert_low=0.5, alert_high=2.0
)
CACHE_HIT_POLICY = RatioPolicy(
    warn_low=0.9, warn_high=1.4, alert_low=0.7, alert_high=2.0
)
DEFAULT_RATIO_POLICY = RatioPolicy(
    warn_low=0.8, warn_high=1.3, alert_low=0.66, alert_high=1.5
)
PRICE_POLICY = RatioPolicy(warn_low=0.9, warn_high=1.2, alert_low=0.66, alert_high=1.5)
TOOL_CALLS_IN_PARALLEL_POLICY = RatioPolicy(
    warn_low=0.9, warn_high=1.4, alert_low=0.7, alert_high=3.0
)
FORMAL_VERIFICATION_POLICY = RatioPolicy(
    warn_low=0.8, warn_high=1.3, alert_low=0.7, alert_high=1.4
)
COVERAGE_ALL_POLICY = RatioPolicy(
    warn_low=0.9, warn_high=1.2, alert_low=0.8, alert_high=1.3
)
COVERAGE_NON_NULL_POLICY = RatioPolicy(
    warn_low=0.9, warn_high=1.2, alert_low=0.8, alert_high=1.3
)


def _has_judge_review(point: Dict, metric_name: str) -> bool:
    metric_data = point.get(metric_name, {}) or {}
    review = metric_data.get(FieldNames.JUDGE_REVIEW)
    return isinstance(review, str) and len(review.strip()) > 0


def _has_all_judge_reviews(point: Dict, metric_names: List[str]) -> bool:
    return all(_has_judge_review(point, metric_name) for metric_name in metric_names)


def _sample_shared_keys_prioritizing_complete_reviews(
    run_data: RunData,
    metric_names: List[str],
) -> List[str]:
    shared_keys = sorted(set(run_data.dataset1.keys()) & set(run_data.dataset2.keys()))
    keys_with_full_reviews = [
        key
        for key in shared_keys
        if _has_all_judge_reviews(run_data.dataset1[key], metric_names)
        and _has_all_judge_reviews(run_data.dataset2[key], metric_names)
    ]
    keys_with_full_reviews_set = set(keys_with_full_reviews)
    remaining_keys = [
        key for key in shared_keys if key not in keys_with_full_reviews_set
    ]

    rng = random.Random(42)
    rng.shuffle(keys_with_full_reviews)
    rng.shuffle(remaining_keys)
    return sorted(
        (keys_with_full_reviews + remaining_keys)[:MAX_LLM_REVIEWED_POOL_SIZE]
    )


def compare_tool_call_count(run_data: RunData) -> ScalarMetricsComparison:
    report_key = FieldNames.TOOL_CALL_COUNT_REPORT
    p_value = safe_mannwhitneyu(
        [
            sum(p[FieldNames.TOOL_CALL_COUNT_DATASET])
            for p in run_data.dataset1.values()
        ],
        [
            sum(p[FieldNames.TOOL_CALL_COUNT_DATASET])
            for p in run_data.dataset2.values()
        ],
    )

    ratio = safe_ratio(run_data.report2[report_key], run_data.report1[report_key])
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=p_value, policy=TOOL_CALLS_COUNT_POLICY
    )

    return ScalarMetricsComparison(
        name=report_key,
        p_value=p_value,
        metrics_value1=run_data.report1[report_key],
        metrics_value2=run_data.report2[report_key],
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_gen_tokens(run_data: RunData) -> ScalarMetricsComparison:
    dataset_key = FieldNames.AGENT_GENERATION_TOKENS
    gen_tokens_per_point1 = [
        sum(sum(p[dataset_key], [])) for p in run_data.dataset1.values()
    ]
    gen_tokens_per_point2 = [
        sum(sum(p[dataset_key], [])) for p in run_data.dataset2.values()
    ]
    p_value = safe_mannwhitneyu(gen_tokens_per_point1, gen_tokens_per_point2)

    tokens1 = sum(gen_tokens_per_point1)
    tokens2 = sum(gen_tokens_per_point2)
    ratio = safe_ratio(tokens2, tokens1)
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=p_value, policy=GEN_TOKENS_POLICY
    )

    return ScalarMetricsComparison(
        name="generation_tokens",
        p_value=p_value,
        metrics_value1=tokens1,
        metrics_value2=tokens2,
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_cache_hit(run_data: RunData) -> ScalarMetricsComparison:
    hit_tokens_key = FieldNames.AGENT_CACHE_HIT_TOKENS
    input_tokens_key = FieldNames.AGENT_INPUT_TOKENS

    def _hit_ratios(point: Dict) -> List[float]:
        return [
            round(
                sum(point[hit_tokens_key][i])
                / (sum(point[input_tokens_key][i]) + 1e-9),
                3,
            )
            for i in range(len(point[input_tokens_key]))
        ]

    per_point1 = [safe_mean(_hit_ratios(p)) for p in run_data.dataset1.values()]
    per_point2 = [safe_mean(_hit_ratios(p)) for p in run_data.dataset2.values()]

    p_value = safe_mannwhitneyu(per_point1, per_point2)
    mean_hit1 = safe_mean(per_point1)
    mean_hit2 = safe_mean(per_point2)

    ratio = safe_ratio(mean_hit2, mean_hit1)
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=p_value, policy=CACHE_HIT_POLICY
    )

    return ScalarMetricsComparison(
        name="cache_hit_mean_ratio",
        p_value=p_value,
        metrics_value1=mean_hit1,
        metrics_value2=mean_hit2,
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_formal_verification(run_data: RunData) -> ScalarMetricsComparison:
    dataset_key = FieldNames.FORMAL_VERIFICATION_RESULT
    successes1 = sum(p[dataset_key] for p in run_data.dataset1.values())
    successes2 = sum(p[dataset_key] for p in run_data.dataset2.values())
    total = len(run_data.dataset1)

    _, p_value = fisher_exact(
        [[successes1, total - successes1], [successes2, total - successes2]],
        alternative="two-sided",
    )

    ratio = safe_ratio(successes2, successes1)
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=float(p_value), policy=FORMAL_VERIFICATION_POLICY
    )

    return ScalarMetricsComparison(
        name=FieldNames.FORMAL_VERIFICATION_RESULT,
        p_value=round(float(p_value), 5),
        metrics_value1=successes1,
        metrics_value2=successes2,
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def _compare_average_test_metric(
    run_data: RunData,
    values1: List[float],
    values2: List[float],
    metric_name: str,
    policy: RatioPolicy,
) -> ScalarMetricsComparison:
    p_value = safe_mannwhitneyu(values1, values2)
    mean1 = run_data.report1.get(metric_name, {}).get("average", 0.0)
    mean2 = run_data.report2.get(metric_name, {}).get("average", 0.0)
    ratio = safe_ratio(mean2, mean1)
    warning_flag, alert_flag = ratio_flags(ratio=ratio, p_value=p_value, policy=policy)
    return ScalarMetricsComparison(
        name=metric_name,
        p_value=p_value,
        metrics_value1=mean1,
        metrics_value2=mean2,
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def _compare_runnable_test_classes(
    test_metrics1: List[Dict[str, float]], test_metrics2: List[Dict[str, float]]
) -> ScalarMetricsComparison:
    runnable_values1 = [
        metrics[FieldNames.RUNNABLE_TEST_CLASSES] for metrics in test_metrics1
    ]
    runnable_values2 = [
        metrics[FieldNames.RUNNABLE_TEST_CLASSES] for metrics in test_metrics2
    ]
    runnable_successes1 = int(sum(runnable_values1))
    runnable_successes2 = int(sum(runnable_values2))
    runnable_total = max(len(runnable_values1), len(runnable_values2))
    runnable_p_value: Optional[float] = None
    if runnable_total > 0:
        _, fisher_p_value = fisher_exact(
            [
                [runnable_successes1, runnable_total - runnable_successes1],
                [runnable_successes2, runnable_total - runnable_successes2],
            ],
            alternative="two-sided",
        )
        runnable_p_value = round(float(fisher_p_value), 5)
    runnable_ratio = safe_ratio(runnable_successes2, runnable_successes1)
    runnable_warning_flag, runnable_alert_flag = ratio_flags(
        ratio=runnable_ratio,
        p_value=runnable_p_value,
        policy=FORMAL_VERIFICATION_POLICY,
    )
    return ScalarMetricsComparison(
        name=FieldNames.RUNNABLE_TEST_CLASSES,
        p_value=runnable_p_value,
        metrics_value1=runnable_successes1,
        metrics_value2=runnable_successes2,
        warning_flag=runnable_warning_flag,
        alert_flag=runnable_alert_flag,
    )


def _compare_non_null_coverage(
    test_metrics1: List[Dict[str, float]], test_metrics2: List[Dict[str, float]]
) -> ScalarMetricsComparison:
    non_null_coverage1 = [
        metrics[FieldNames.COVERAGE]
        for metrics in test_metrics1
        if metrics[FieldNames.COVERAGE] != 0
    ]
    non_null_coverage2 = [
        metrics[FieldNames.COVERAGE]
        for metrics in test_metrics2
        if metrics[FieldNames.COVERAGE] != 0
    ]
    p_value_non_null = safe_mannwhitneyu(non_null_coverage1, non_null_coverage2)
    mean_non_null1 = safe_mean(non_null_coverage1)
    mean_non_null2 = safe_mean(non_null_coverage2)
    ratio_non_null = safe_ratio(mean_non_null2, mean_non_null1)
    warn_non_null, alert_non_null = ratio_flags(
        ratio=ratio_non_null,
        p_value=p_value_non_null,
        policy=COVERAGE_NON_NULL_POLICY,
    )
    return ScalarMetricsComparison(
        name="coverage_non_null",
        p_value=p_value_non_null,
        metrics_value1=mean_non_null1,
        metrics_value2=mean_non_null2,
        warning_flag=warn_non_null,
        alert_flag=alert_non_null,
    )


def compare_test_metrics(run_data: RunData) -> List[ScalarMetricsComparison]:
    test_metrics1 = [
        extract_test_metrics(point) for point in run_data.dataset1.values()
    ]
    test_metrics2 = [
        extract_test_metrics(point) for point in run_data.dataset2.values()
    ]

    mean_metric_comparisons = []
    for metric_name in [FieldNames.PASSED_TESTS_FRACTION, FieldNames.COVERAGE]:
        mean_metric_comparisons.append(
            _compare_average_test_metric(
                run_data,
                [metrics[metric_name] for metrics in test_metrics1],
                [metrics[metric_name] for metrics in test_metrics2],
                metric_name,
                COVERAGE_ALL_POLICY,
            )
        )

    return [
        _compare_runnable_test_classes(test_metrics1, test_metrics2),
        *mean_metric_comparisons,
        _compare_non_null_coverage(test_metrics1, test_metrics2),
    ]


def compare_tool_calls_in_parallel(run_data: RunData) -> ScalarMetricsComparison:
    report_key = FieldNames.TOOL_CALLS_IN_PARALLEL

    ratio = safe_ratio(run_data.report2[report_key], run_data.report1[report_key])
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=None, policy=TOOL_CALLS_IN_PARALLEL_POLICY
    )

    return ScalarMetricsComparison(
        name="tool_calls_in_parallel_mean",
        p_value=None,
        metrics_value1=run_data.report1[report_key],
        metrics_value2=run_data.report2[report_key],
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_price(run_data: RunData) -> ScalarMetricsComparison:
    total1 = run_data.report1[FieldNames.AGENT_PRICE_PER_INTERACTION]["total"]
    total2 = run_data.report2[FieldNames.AGENT_PRICE_PER_INTERACTION]["total"]
    dataset_key = FieldNames.AGENT_PRICE_PER_INTERACTION
    p_value = safe_mannwhitneyu(
        [sum(p[dataset_key]) for p in run_data.dataset1.values()],
        [sum(p[dataset_key]) for p in run_data.dataset2.values()],
    )

    ratio = safe_ratio(total2, total1)
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=p_value, policy=PRICE_POLICY
    )

    return ScalarMetricsComparison(
        name="price",
        p_value=p_value,
        metrics_value1=total1,
        metrics_value2=total2,
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_time(run_data: RunData) -> ScalarMetricsComparison:
    total1 = run_data.report1[FieldNames.AGENT_TIME_PER_INTERACTION]["total"]
    total2 = run_data.report2[FieldNames.AGENT_TIME_PER_INTERACTION]["total"]
    dataset_key = FieldNames.AGENT_TIME_PER_INTERACTION
    p_value = safe_mannwhitneyu(
        [sum(p[dataset_key]) for p in run_data.dataset1.values()],
        [sum(p[dataset_key]) for p in run_data.dataset2.values()],
    )

    ratio = safe_ratio(total2, total1)
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio, p_value=p_value, policy=DEFAULT_RATIO_POLICY
    )

    return ScalarMetricsComparison(
        name="time",
        p_value=p_value,
        metrics_value1=total1,
        metrics_value2=total2,
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_gen_tokens_to_seconds_ratio(run_data: RunData) -> ScalarMetricsComparison:
    report_key = FieldNames.GEN_TOKENS_TO_SECONDS_RATIO

    def _get_point_ratio(point: Dict) -> float:
        return sum(sum(point[FieldNames.AGENT_GENERATION_TOKENS], [])) / (
            sum(point[FieldNames.AGENT_TIME_PER_INTERACTION]) + 1e-9
        )

    p_value = safe_mannwhitneyu(
        [_get_point_ratio(p) for p in run_data.dataset1.values()],
        [_get_point_ratio(p) for p in run_data.dataset2.values()],
    )
    ratio = safe_ratio(run_data.report2[report_key], run_data.report1[report_key])
    warning_flag, alert_flag = ratio_flags(
        ratio=ratio,
        p_value=p_value,
        policy=DEFAULT_RATIO_POLICY,
    )

    return ScalarMetricsComparison(
        name=report_key,
        p_value=p_value,
        metrics_value1=run_data.report1[report_key],
        metrics_value2=run_data.report2[report_key],
        warning_flag=warning_flag,
        alert_flag=alert_flag,
    )


def compare_tool_success(run_data: RunData) -> List[ToolMetricsComparison]:
    def _parse_fraction(frac: str):
        success, total = frac.split("/")
        return int(success), int(total)

    comps: List[ToolMetricsComparison] = []
    tools1 = run_data.report1[FieldNames.TOOL_CALLS_SUCCESS_RATES]
    tools2 = run_data.report2[FieldNames.TOOL_CALLS_SUCCESS_RATES]

    tools = sorted(set(list(tools1.keys()) + list(tools2.keys())))

    for tool in tools:
        success1, total1 = _parse_fraction(tools1.get(tool, "0/0"))
        success2, total2 = _parse_fraction(tools2.get(tool, "0/0"))
        ratio1 = success1 / total1 if total1 > 0 else 0
        ratio2 = success2 / total2 if total2 > 0 else 0

        if total2 <= 3:
            comps.append(
                ToolMetricsComparison(
                    name=f"{tool}_success_rates",
                    p_value=None,
                    metrics_value1=ratio1,
                    metrics_value2=ratio2,
                    total_count1=total1,
                    total_count2=total2,
                    warning_flag=False,
                    alert_flag=False,
                )
            )
            continue

        rel_change = None
        if total1 > 0 and total2 > 0:
            rel_change = ratio2 / (ratio1 + 1e-9)

        warning = False
        alert = False

        if total2 >= 20:
            warn_rel = 0.9
            alert_rel = 0.8
        elif total2 >= 10:
            warn_rel = 0.8
            alert_rel = 0.6
        else:
            warn_rel = 0.7
            alert_rel = 0.4

        if rel_change is not None:
            if rel_change < warn_rel or rel_change > 1.2 / warn_rel:
                warning = True
            if rel_change < alert_rel or rel_change > 1.2 / warn_rel:
                alert = True

        if total1 > 0:
            rel_calls_change = total2 / total1
            abs_calls_diff = abs(total2 - total1)
            if (
                rel_calls_change < 0.7 or rel_calls_change > 1.4
            ) and abs_calls_diff >= 12:
                warning = True

        comps.append(
            ToolMetricsComparison(
                name=f"{tool}_success_rates",
                p_value=None,
                metrics_value1=ratio1,
                metrics_value2=ratio2,
                total_count1=total1,
                total_count2=total2,
                warning_flag=warning,
                alert_flag=alert,
            )
        )
    return comps


def compare_termination_reasons(run_data: RunData) -> TerminationReasonsComparison:
    reasons1 = run_data.report1.get(FieldNames.TERMINATION_REASON, {})
    reasons2 = run_data.report2.get(FieldNames.TERMINATION_REASON, {})

    all_reasons = set(reasons1.keys()) | set(reasons2.keys())

    union_size = 0.0
    diff_size = 0.0

    for reason in all_reasons:
        c1 = float(reasons1.get(reason, 0) or 0)
        c2 = float(reasons2.get(reason, 0) or 0)
        union_size += max(c1, c2)
        diff_size += abs(c1 - c2)

    warning = diff_size >= union_size / 5.0 + 2.0
    alert = diff_size >= union_size / 4.0 + 3.0

    common: Dict[str, int] = {}
    diff1: Dict[str, int] = {}
    diff2: Dict[str, int] = {}

    for reason in sorted(all_reasons):
        c1 = int(reasons1.get(reason, 0) or 0)
        c2 = int(reasons2.get(reason, 0) or 0)
        shared = min(c1, c2)
        extra1 = max(c1 - shared, 0)
        extra2 = max(c2 - shared, 0)

        if shared > 0:
            common[reason] = shared
        if extra1 > 0:
            diff1[reason] = extra1
        if extra2 > 0:
            diff2[reason] = extra2

    return TerminationReasonsComparison(
        name=FieldNames.TERMINATION_REASON,
        warning_flag=warning,
        alert_flag=alert,
        common=common,
        diff1=diff1,
        diff2=diff2,
    )


def compare_judge_metrics_trajectory_based(
    run_data: RunData, config: Dict, bench_tag_name: str, api_key: str
) -> Tuple[List[JudgeMetricsComparison], Dict[str, str], Dict[str, Dict[str, str]]]:
    comparisons: List[JudgeMetricsComparison] = []
    judge_summary_dialogues: Dict[str, str] = {}
    judge_comparison_dialogues: Dict[str, Dict[str, str]] = {}
    metrics_list = AgentScenarioTags.get_pairwise_llm_judge_metrics_for_tag(
        bench_tag_name
    )

    metric_names = [metric_cls.get_name() for metric_cls in metrics_list]
    shuffled_keys = _sample_shared_keys_prioritizing_complete_reviews(
        run_data, metric_names
    )

    for metric_cls in metrics_list:
        metrics_name = metric_cls.get_name()
        if metrics_name not in run_data.report1 or metrics_name not in run_data.report2:
            continue

        metric = metric_cls(config, api_key=api_key, ordered_keys=shuffled_keys)
        summary_cmp, dialogue, per_task, per_task_dialogues = metric.compare(
            run_data.dataset1, run_data.dataset2
        )
        comparison_name = f"Comparison for {metrics_name}"
        judge_summary_dialogues[comparison_name] = dialogue
        judge_comparison_dialogues[comparison_name] = per_task_dialogues

        scores = [c.score for c in per_task if c.score is not None]
        mean_score = safe_mean(scores)
        p_value = paired_permutation_test(scores)

        score_cmp = PairwiseScalarComparison(
            name="Scoring",
            p_value=p_value,
            metrics_value=mean_score,
            warning_flag=mean_score <= -0.2 or mean_score >= 0.3,
            alert_flag=p_value < 0.05 or mean_score <= -0.4 or mean_score >= 0.5,
        )

        comparisons.append(
            JudgeMetricsComparison(
                name=f"{metrics_name}_Judge",
                text_cmp=summary_cmp,
                score_comparison=score_cmp,
                warning_flag=summary_cmp.judge_alert or score_cmp.alert_flag,
                alert_flag=score_cmp.alert_flag and summary_cmp.judge_alert,
            )
        )

    return comparisons, judge_summary_dialogues, judge_comparison_dialogues


def compare_setups(run_data: RunData, data_conformity_report: Dict) -> SetupComparison:
    data_conformity_errors = data_conformity_report["errors"]
    return SetupComparison(
        alert_flag=True if data_conformity_errors else False,
        difference="\n".join(data_conformity_errors)
        if data_conformity_errors
        else "unchecked",
    )
