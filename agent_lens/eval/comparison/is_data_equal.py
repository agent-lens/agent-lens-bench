from typing import Dict, Any, Set

from agent_lens.eval.metrics.tag_to_metrics import AgentScenarioTags
from agent_lens.eval.comparison.io.runs_loader import get_runs_data_for_tag
from agent_lens.eval.comparison.compute.models import RunData


def _compare_keys(
    dict1: Dict, dict2: Dict, judge_metrics: Set[str], results: Dict, context: str = ""
) -> None:
    """Helper function to compare keys in dictionaries."""
    keys1 = set(dict1.keys()) if isinstance(dict1, dict) else set()
    keys2 = set(dict2.keys()) if isinstance(dict2, dict) else set()

    non_judge_keys1 = keys1 - judge_metrics
    non_judge_keys2 = keys2 - judge_metrics

    # Check if non-judge keys are the same
    if non_judge_keys1 != non_judge_keys2:
        missing_in_1 = non_judge_keys2 - non_judge_keys1
        missing_in_2 = non_judge_keys1 - non_judge_keys2
        if missing_in_1:
            results["warnings"].append(
                f"Non-judge keys missing in {context} (first): {missing_in_1}"
            )
        if missing_in_2:
            results["warnings"].append(
                f"Non-judge keys missing in {context} (second): {missing_in_2}"
            )

    judge_keys1 = keys1.intersection(judge_metrics)
    judge_keys2 = keys2.intersection(judge_metrics)

    if judge_keys1 != judge_keys2:
        results["warnings"].append(
            f"Judge metrics differ in {context}: "
            f"dict1 has {judge_keys1}, dict2 has {judge_keys2}"
        )


def _compare_field_values(
    dict1: Dict, dict2: Dict, field_name: str, results: Dict, context: str = ""
) -> None:
    """Helper function to compare specific field values in dictionaries."""
    value1 = dict1.get(field_name)
    value2 = dict2.get(field_name)

    if value1 != value2:
        prefix = f"{context}." if context else ""
        results["errors"].append(
            f"{prefix}{field_name} differs: dict1={value1}, dict2={value2}"
        )


class DataManagerForTag:
    def __init__(self, config, bench_tag_name: str):
        self.run_data = get_runs_data_for_tag(config, bench_tag_name)
        self.llm_judge_metrics = AgentScenarioTags.get_all_llm_judge_metrics()

    def get_run_data_for_tag(self) -> Dict[str, RunData]:
        return self.run_data

    def do_runs_conform(self, run_data: RunData, language: str) -> Dict[str, Any]:
        results = {
            "datasets_compatible": True,
            "errors": [],
            "warnings": [],
            "should_align": False,
        }

        keys1 = set(run_data.dataset1.keys())
        keys2 = set(run_data.dataset2.keys())

        if keys1 != keys2:
            missing_in_1 = keys2 - keys1
            missing_in_2 = keys1 - keys2
            if missing_in_1:
                results["errors"].append(
                    f"Points missing in dataset1 for {language} language: {missing_in_1}"
                )
            if missing_in_2:
                results["errors"].append(
                    f"Points missing in dataset2 for {language} language: {missing_in_2}"
                )
            results["datasets_compatible"] = False
            results["should_align"] = True

        common_keys = keys1.intersection(keys2)
        for key in common_keys:
            try:
                self._compare_scenario_keys(
                    run_data.dataset1[key],
                    run_data.dataset2[key],
                    key,
                    results,
                )
            except Exception as e:
                results["errors"].append(f"Error comparing scenario '{key}': {str(e)}")
                results["datasets_compatible"] = False

        # Compare report files if paths are provided
        self._compare_reports(run_data.report1, run_data.report2, results)

        if results["errors"]:
            results["datasets_compatible"] = False
        return results

    def _compare_scenario_keys(
        self, scenario1: Dict, scenario2: Dict, scenario_key: str, results: Dict
    ):
        _compare_keys(
            scenario1,
            scenario2,
            set(m.get_name() for m in self.llm_judge_metrics),
            results,
            f"dataset['{scenario_key}']",
        )

    def _compare_reports(self, report1: Dict, report2: Dict, results: Dict):
        try:
            # Compare top-level keys in reports, treating judge metrics separately
            _compare_keys(
                report1,
                report2,
                set(m.get_name() for m in self.llm_judge_metrics),
                results,
                "report",
            )

            # Compare specific report fields
            _compare_field_values(report1, report2, "chats_count", results, "report")
            _compare_field_values(report1, report2, "judge", results, "report")
        except Exception as e:
            results["errors"].append(f"Error comparing reports: {str(e)}")
