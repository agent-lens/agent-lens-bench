import argparse
import logging
from pathlib import Path

from agent_lens.eval.common.json_io import write_json
from agent_lens.eval.common.logging_setup import suppress_httpx_warnings
from agent_lens.eval.common.paths import sanitize_path_component
from agent_lens.eval.common.time import get_nice_time
from agent_lens.eval.common.yaml_io import load_yaml_mapping
from agent_lens.eval.data_framework.compute.dataset_builder import (
    dumps_to_dataset,
)
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.metrics.llm_judge.custom_question import (
    CustomQuestionMetric,
)
from agent_lens.eval.metrics.llm_judge.common.prompt_builders import (
    PROMPT_RESPONSE_SEPARATOR,
)
from agent_lens.eval.metrics.llm_judge.common.review_style_user import (
    get_review_timezone,
)

LOG = logging.getLogger(__name__)

suppress_httpx_warnings()


def parse_cmd_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config_path",
        default="agent_lens/eval/configs/agent_bench_config.yaml",
        help="Path to config file for the python benchmark",
        type=str,
    )
    parser.add_argument(
        "-k",
        "--api_key",
        help="API key for an LLM chosen as a judge model (required; may be empty only when judge_provider == openai_compatible)",
        required=True,
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
        help="Output: folder where the result will be written",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--question",
        required=True,
        help="Custom question to ask the LLM judge for each point and in aggregation",
        type=str,
    )
    parser.add_argument(
        "--language",
        required=False,
        help="Programming language of the agent, java by default",
        type=str,
        default="java",
    )
    return parser.parse_args()


def run_answer_based_on_data(
    *,
    config_path: str,
    idea_logs_path: str,
    dump_dir: str,
    question: str,
    language: str,
    api_key: str,
) -> None:
    config = load_yaml_mapping(config_path, strict=True)

    # Inject the question into the config so the metric can access it
    config["custom_question"] = question

    dataset = dumps_to_dataset(idea_logs_path)[language]

    # Run metric and collect raw per-point responses
    metrics = CustomQuestionMetric(config, api_key=api_key)
    metrics.select_points(dataset)
    metrics.compute_single_run_reviews()

    per_point = {}
    for idx, point in metrics.data.items():  # noqa: SLF001 (intentional internal access)
        dialogue = point[metrics.get_name()][FieldNames.JUDGE_DIALOGUE]
        per_point[str(idx)] = dialogue.split(PROMPT_RESPONSE_SEPARATOR)[-1].strip()

    # Get raw aggregate LLM review (reuse aggregate() to build the prompt, discard stats)
    aggregated = metrics.single_run_aggregate()
    aggregate_response = aggregated[metrics.get_name()]["llm review"]

    result = {
        "per_point": per_point,
        "aggregate": aggregate_response,
    }

    # Save a minimal JSON with only raw responses, and also print to stdout
    dump_dir_path = Path(dump_dir)
    dump_dir_path.mkdir(parents=True, exist_ok=True)

    time_str = get_nice_time(get_review_timezone(config))
    question_prefix = sanitize_path_component(question)[:40].strip() or "question"
    out_path = dump_dir_path / f"{question_prefix}_{time_str}.json"
    write_json(out_path, result)

    LOG.info(result["aggregate"])


def main() -> None:
    args = parse_cmd_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_answer_based_on_data(
        config_path=args.config_path,
        idea_logs_path=args.idea_logs_path,
        dump_dir=args.dump_dir,
        question=args.question,
        language=args.language,
        api_key=args.api_key,
    )


if __name__ == "__main__":
    main()
