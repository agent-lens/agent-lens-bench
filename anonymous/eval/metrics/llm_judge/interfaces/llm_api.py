import abc
import logging
from hashlib import md5
from threading import Lock
from typing import Dict, Callable, List

from anonymous.eval.common.llm_judge_usage import LlmJudgeUsageTracker
from anonymous.eval.metrics.llm_judge.cache.json_cache import (
    load_json_cache,
    save_json_cache,
)
from anonymous.eval.metrics.llm_judge.common.prompt_builders import (
    LlmJudgeInstructions,
    PROMPT_RESPONSE_SEPARATOR,
)
from anonymous.eval.metrics.llm_judge.providers.openai_compat import (
    resolve_openai_compatible_base_url,
)
from anonymous.eval.metrics.llm_judge.providers.registry import (
    PROVIDER_OPENAI_COMPATIBLE,
    get_judge_provider,
)
from anonymous.eval.metrics.llm_judge.runtime.llm_runtime import (
    call_llm_with_retry_policy,
    run_in_parallel,
)

LOG = logging.getLogger(__name__)


class LlmApi(abc.ABC):
    def __init__(self, config_dict: Dict, api_key: str) -> None:
        self.config_dict = config_dict
        self.api_key = api_key
        self.llm_single_query = self._create_llm_single_query_func()
        self.max_num_API_requests = config_dict["max_num_API_requests"]
        self.max_parallel_requests = config_dict.get("max_parallel_requests", 50)
        self.failed_with_flex_tier = False
        self.cache_path = config_dict.get("cache_path", "./cache.json")
        self.cache = {}
        self.cache_save_count = 0
        self.cache_save_interval = config_dict.get("cache_save_interval", 5)
        self.lock = Lock()

    def _load_cache(self) -> Dict:
        return load_json_cache(self.cache_path)

    def _save_cache(self) -> None:
        save_json_cache(cache_path=self.cache_path, cache=self.cache)

    @staticmethod
    def _get_cache_key(
        model_name: str, provider: str, base_url: str, user_prompt: str
    ) -> str:
        return (
            f"{model_name}@{provider}:{base_url}:"
            f"{md5(user_prompt.encode()).hexdigest()}"
        )

    def _save_cache_periodically(self) -> None:
        self.cache_save_count += 1
        if self.cache_save_count >= self.cache_save_interval:
            self._save_cache()
            self.cache_save_count = 0

    def _create_llm_single_query_func(self) -> Callable:
        """Create a function that calls the configured LLM judge provider.

        The returned function takes a user prompt and returns the model's content.

        Raises:
            RuntimeError: If the run-wide API call budget is exceeded.
            ValueError: If the configured judge model/provider is invalid.
        """
        config_dict = self.config_dict

        provider = get_judge_provider(config_dict)
        base_url = (
            resolve_openai_compatible_base_url(config_dict)
            if provider == PROVIDER_OPENAI_COMPATIBLE
            else ""
        )

        # API keys are wired by CLI/pipeline.

        system_prompt = LlmJudgeInstructions.SYSTEM_PROMPT

        def llm_single_query(user_prompt: str) -> str:
            cache_key = self._get_cache_key(
                config_dict["judge_model"], provider, base_url, user_prompt
            )

            with self.lock:
                if cache_key in self.cache:
                    return self.cache[cache_key]

                # Reserve a run-wide API call budget slot (cache hits excluded).
                LlmJudgeUsageTracker.reserve_api_call(
                    max_requests=self.max_num_API_requests
                )

            (
                content,
                prompt_tokens,
                completion_tokens,
                cached_prompt_tokens,
                self.failed_with_flex_tier,
            ) = call_llm_with_retry_policy(
                config_dict=config_dict,
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                failed_with_flex_tier=self.failed_with_flex_tier,
                api_key=self.api_key,
            )

            LlmJudgeUsageTracker.increment_prompt_usage(prompt_tokens)
            LlmJudgeUsageTracker.increment_cached_prompt_usage(cached_prompt_tokens)
            LlmJudgeUsageTracker.increment_completion_usage(completion_tokens)

            with self.lock:
                self.cache[cache_key] = content
                self._save_cache_periodically()

            return content

        return llm_single_query

    def _process_message(self, message: str) -> str:
        """Helper function to process one message with the LLM."""
        response = self.llm_single_query(message)
        return message + PROMPT_RESPONSE_SEPARATOR + response

    def get_llm_responses(self, user_messages: List[str]) -> List[str]:
        """Takes in a list of user messages for all data points.
        Feeds each user message to LLM in parallel.
        """
        LOG.info(
            "%s: Sending %d request(s) to LLM...",
            self.get_name(),
            len(user_messages),
        )
        self.cache = self._load_cache()
        dialogues = run_in_parallel(
            user_messages=user_messages,
            process_message=self._process_message,
            max_workers=self.max_parallel_requests,
        )
        self._save_cache()
        return dialogues

    def get_llm_response(self, user_message: str) -> str:
        return self.get_llm_responses([user_message])[0]

    @staticmethod
    @abc.abstractmethod
    def get_name() -> str:
        pass
