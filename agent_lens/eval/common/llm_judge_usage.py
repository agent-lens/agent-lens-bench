import abc
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Iterator, Union


@dataclass(frozen=True)
class LlmJudgeUsage:
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    api_calls: int

    def delta(self, before: "LlmJudgeUsage") -> "LlmJudgeUsage":
        return LlmJudgeUsage(
            prompt_tokens=self.prompt_tokens - before.prompt_tokens,
            cached_tokens=self.cached_tokens - before.cached_tokens,
            completion_tokens=self.completion_tokens - before.completion_tokens,
            api_calls=self.api_calls - before.api_calls,
        )

    def price_usd(self, *, judge: str, flex_service_tier: bool) -> Union[float, str]:
        return LlmJudgeUsageTracker.get_price_for_usage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cached_prompt_tokens=self.cached_tokens,
            judge=judge,
            flex_service_tier=flex_service_tier,
        )


@dataclass
class LlmJudgeUsageCapture:
    usage: LlmJudgeUsage = LlmJudgeUsage(
        prompt_tokens=0,
        cached_tokens=0,
        completion_tokens=0,
        api_calls=0,
    )


class LlmJudgeUsageTracker(abc.ABC):
    # NOTE: usage is accumulated globally for the current process.
    # If multiple runs share a process, the counters must be interpreted as process-local state.
    _lock = Lock()

    # Token usage is accumulated globally and read as deltas by pipeline-level helpers.
    prompt_tokens_usage = 0
    completion_tokens_usage = 0

    cached_prompt_tokens_usage = 0

    api_calls_usage = 0

    # Prices are in USD per 1M tokens.
    token_price = {
        "gpt-5.4": {
            "input": 2.5,
            "output": 15.0,
            "cached_input_multiplier": 0.1,
        },
        "OpenAI/gpt-5.4": {
            "input": 2.5,
            "output": 15.0,
            "cached_input_multiplier": 0.1,
        },
        "gpt-5-nano": {
            "input": 0.05,
            "output": 0.4,
            "cached_input_multiplier": 0.1,
        },
    }

    @staticmethod
    def get_usage() -> LlmJudgeUsage:
        with LlmJudgeUsageTracker._lock:
            return LlmJudgeUsage(
                prompt_tokens=LlmJudgeUsageTracker.prompt_tokens_usage,
                cached_tokens=LlmJudgeUsageTracker.cached_prompt_tokens_usage,
                completion_tokens=LlmJudgeUsageTracker.completion_tokens_usage,
                api_calls=LlmJudgeUsageTracker.api_calls_usage,
            )

    @staticmethod
    def reserve_api_call(*, max_requests: int) -> int:
        """Reserve a single API call, enforcing a run-wide max budget."""
        if max_requests < 0:
            raise ValueError("max_requests must be non-negative")
        with LlmJudgeUsageTracker._lock:
            if LlmJudgeUsageTracker.api_calls_usage >= max_requests:
                raise RuntimeError(
                    f"Maximum number of API requests ({max_requests}) reached. "
                    'Change "max_num_API_requests" in config.'
                )
            LlmJudgeUsageTracker.api_calls_usage += 1
            return LlmJudgeUsageTracker.api_calls_usage

    @staticmethod
    def increment_prompt_usage(token_count: int) -> None:
        with LlmJudgeUsageTracker._lock:
            LlmJudgeUsageTracker.prompt_tokens_usage += token_count

    @staticmethod
    def increment_completion_usage(token_count: int) -> None:
        with LlmJudgeUsageTracker._lock:
            LlmJudgeUsageTracker.completion_tokens_usage += token_count

    @staticmethod
    def increment_cached_prompt_usage(token_count: int) -> None:
        with LlmJudgeUsageTracker._lock:
            LlmJudgeUsageTracker.cached_prompt_tokens_usage += token_count

    @staticmethod
    def get_price_for_usage(
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int = 0,
        judge: str,
        flex_service_tier: bool,
    ) -> Union[float, str]:
        if judge not in LlmJudgeUsageTracker.token_price:
            return "Unknown"

        prices = LlmJudgeUsageTracker.token_price[judge]
        input_cost = prices["input"]
        output_cost = prices["output"]
        cached_input_multiplier = prices.get("cached_input_multiplier", 1.0)

        cached_prompt_tokens = max(
            0, min(int(cached_prompt_tokens), int(prompt_tokens))
        )
        non_cached_prompt_tokens = int(prompt_tokens) - cached_prompt_tokens

        price = (
            non_cached_prompt_tokens * input_cost
            + cached_prompt_tokens * input_cost * cached_input_multiplier
            + int(completion_tokens) * output_cost
        )
        if flex_service_tier:
            price /= 2
        return price / 10**6

    @staticmethod
    @contextmanager
    def capture_usage_delta() -> Iterator[LlmJudgeUsageCapture]:
        usage_before = LlmJudgeUsageTracker.get_usage()
        capture = LlmJudgeUsageCapture()
        try:
            yield capture
        finally:
            capture.usage = LlmJudgeUsageTracker.get_usage().delta(usage_before)
