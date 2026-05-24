from typing import Dict, List, Type

from anonymous.eval.metrics.tag_names import TagNames
from anonymous.eval.metrics.llm_judge.end_result import EndResultMetric
from anonymous.eval.metrics.llm_judge.instruction_compliance import (
    InstructionComplianceMetric,
)
from anonymous.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from anonymous.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)
from anonymous.eval.metrics.llm_judge.pitfalls import PitfallsMetric
from anonymous.eval.metrics.llm_judge.pleasantness import PleasantnessMetric
from anonymous.eval.metrics.llm_judge.tool_calls import ToolCallsMetric
from anonymous.eval.metrics.llm_judge.maintainability import (
    TestMaintainabilityMetric,
)
from anonymous.eval.metrics.llm_judge.mocking_reliance import (
    RelianceOnMockingMetric,
)
from anonymous.eval.metrics.llm_judge.test_coverage import (
    TestSemanticCoverageMetric,
)
from anonymous.eval.metrics.llm_judge.test_usefulness import (
    TestUsefulnessMetric,
)


class AgentScenarioTags:
    TagToMetrics: Dict[str, List[Type[LlmMetric]]] = {
        TagNames.general: [
            PitfallsMetric,
            PleasantnessMetric,
            ToolCallsMetric,
        ],
        TagNames.workflows: [
            EndResultMetric,
            InstructionComplianceMetric,
            PitfallsMetric,
            PleasantnessMetric,
            ToolCallsMetric,
        ],
        TagNames.testing: [
            PitfallsMetric,
            PleasantnessMetric,
            RelianceOnMockingMetric,
            TestMaintainabilityMetric,
            TestSemanticCoverageMetric,
            TestUsefulnessMetric,
            ToolCallsMetric,
        ],
    }

    @classmethod
    def get_tags(cls) -> set[str]:
        return set(cls.TagToMetrics.keys())

    @classmethod
    def get_llm_judge_metrics_for_tag(
        cls, bench_tag_name: str
    ) -> List[Type[LlmMetric]]:
        metrics_list = cls.TagToMetrics.get(bench_tag_name, [])
        return sorted(set(metrics_list), key=lambda x: x.get_name())

    @classmethod
    def get_pairwise_llm_judge_metrics_for_tag(
        cls, bench_tag_name: str
    ) -> List[Type[PairwiseLlmMetric]]:
        metrics_list = AgentScenarioTags.get_llm_judge_metrics_for_tag(bench_tag_name)
        return [m for m in metrics_list if issubclass(m, PairwiseLlmMetric)]

    @classmethod
    def get_all_llm_judge_metrics(cls) -> List[Type[LlmMetric]]:
        llm_metrics_set = set()
        for tag_name in cls.TagToMetrics.keys():
            llm_metrics_set.update(cls.get_llm_judge_metrics_for_tag(tag_name))
        return sorted(llm_metrics_set, key=lambda x: x.get_name())
