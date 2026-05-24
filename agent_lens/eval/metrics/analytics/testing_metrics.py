from typing import Any, Callable, Mapping

from agent_lens.eval.data_framework.field_names import FieldNames

VERIFIER_RESULTS_KEY = "verifier_results"
SUCCESS_WITH_METRICS_TYPE = "SuccessWithMetrics"
METRICS_KEY = "metrics"
VERIFIER_PASSED_KEY = "passed"
VERIFIER_TESTS_KEY = "tests"
VERIFIER_COVERAGE_KEY = "coverage"


def add_test_metrics_aggregates(
    report: dict[str, Any],
    dataset: Mapping[str, Mapping[str, Any]],
    get_chat_stats: Callable[..., dict[str, float | str]],
) -> dict[str, Any]:
    report[FieldNames.RUNNABLE_TEST_CLASSES] = get_chat_stats(
        [point.get(FieldNames.RUNNABLE_TEST_CLASSES, 0) for point in dataset.values()],
        None,
    )
    report[FieldNames.PASSED_TESTS_FRACTION] = get_chat_stats(
        [point.get(FieldNames.PASSED_TESTS_FRACTION, 0) for point in dataset.values()],
        agg_fun="mean",
    )
    report[FieldNames.COVERAGE] = get_chat_stats(
        [point.get(FieldNames.COVERAGE, 0) for point in dataset.values()],
        agg_fun="mean",
    )
    return report


def extract_test_metrics(point: Mapping[str, Any]) -> dict[str, float]:
    verifier_results = point.get(VERIFIER_RESULTS_KEY, [])
    if not isinstance(verifier_results, list):
        return {}

    for result in verifier_results:
        if not isinstance(result, Mapping):
            continue
        if result.get("type") != SUCCESS_WITH_METRICS_TYPE:
            continue

        metrics = result.get(METRICS_KEY, {})
        if not isinstance(metrics, Mapping):
            continue

        tests_count = metrics.get(VERIFIER_TESTS_KEY, 0)
        passed_count = metrics.get(VERIFIER_PASSED_KEY, 0)
        coverage = metrics.get(VERIFIER_COVERAGE_KEY)
        if coverage is None:
            continue

        passed_fraction = passed_count / tests_count if tests_count else 0.0
        return {
            FieldNames.RUNNABLE_TEST_CLASSES: 1.0,
            FieldNames.PASSED_TESTS_FRACTION: passed_fraction,
            FieldNames.COVERAGE: float(coverage),
        }

    return {
        FieldNames.RUNNABLE_TEST_CLASSES: 0.0,
        FieldNames.PASSED_TESTS_FRACTION: 0.0,
        FieldNames.COVERAGE: 0.0,
    }
