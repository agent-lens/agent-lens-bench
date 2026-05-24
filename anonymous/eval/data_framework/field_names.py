class FieldNames:
    AGENT_BENCH_TAGS = "agent_bench_tags"
    AGENT_CACHE_HIT_TOKENS = "agent_prompt_cache_hit_tokens"
    AGENT_CHAT_DUMP = "agent_chat_dump"
    AGENT_GENERATION_TOKENS = "agent_generation_tokens"
    AGENT_INPUT_TOKENS = "agent_input_tokens"
    AGENT_PRICE_PER_INTERACTION = "agent_price"
    AGENT_SCENARIO_NAME = "scenario_name"
    AGENT_TIME_PER_INTERACTION = "agent_time"
    AGENT_TRACE_PROMPT = "agent_trace_prompt"
    GEN_TOKENS_TO_SECONDS_RATIO = "gen_tokens_to_seconds_ratio"

    # Report-level keys
    FORMAL_VERIFICATION_SUCCESS_RATE = "formal_verification_success_rate"
    PASSED_TESTS_FRACTION = "passed_tests_fraction"
    RUNNABLE_TEST_CLASSES = "runnable_test_classes"
    TOOL_CALLS_PER_CHAT_MEAN = "tools_calls_per_chat_mean"

    ALL_LLM_CALLS = "all_llm_calls"
    COVERAGE = "coverage"
    FORMAL_VERIFICATION_RESULT = "formal_verification_result"

    JUDGE_DIALOGUE = "judge_dialogue"
    JUDGE_REVIEW = "judge_review"
    JUDGE_SCORE = "judge_score"

    LANGUAGE = "language"
    MESSAGE_PATH = "message_path"
    MESSAGE_DUMP_PATH = "message_dump_path"
    MESSAGE_ROLE = "role"

    NUM_AGENT_SCENARIOS = "agent_scenarios_count"
    NUM_CHATS = "chats_count"

    PROJECT = "project_title"
    PROJECTS_RESULTS = "projects_results"

    RESPONSE_ROLE = "role"

    RUN_INFO_DATASET_CONFIG_HASH = "dataset_config_hash"
    RUN_INFO_EXP_NAME = "experiment_name"
    RUN_INFO_MODEL_NAME = "model_name"
    RUN_INFO_PLUGIN_HASH = "plugin_hash"
    RUN_INFO_PROVIDER_NAME = "provider_name"
    RUN_INFO_TIMESTAMP = "timestamp"

    SIMULATOR_NAME = "simulator_name"
    SIMULATOR_RESPONSE_TYPE = "simulator"
    SYSTEM_MESSAGE_TYPE = "system"

    TERMINATION_REASON = "termination_reason"

    TOOL_CALLS_DUMP = "tool_calls_dump"
    TOOL_CALLS_IN_PARALLEL = "tool_calls_in_parallel_mean"
    TOOL_CALLS_SUCCESS_RATES = "tool_call_success_rates"
    TOOL_CALL_COUNT_DATASET = "agent_tool_calls_num"
    TOOL_CALL_COUNT_REPORT = "tools_calls_total"
