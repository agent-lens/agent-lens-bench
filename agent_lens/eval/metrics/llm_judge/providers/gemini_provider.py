from types import SimpleNamespace
from typing import Any, Dict

from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig

_ZERO_USAGE_METADATA = SimpleNamespace(prompt_token_count=0, total_token_count=0)


def get_gemini_response(
    config_dict: Dict, system_prompt: str, user_prompt: str, api_key: str
) -> Any:
    client = genai.Client(api_key=api_key)

    if config_dict["judge_model"] == "gemini-2.5-pro":
        judge_model = "gemini-2.5-pro-preview-05-06"
    elif config_dict["judge_model"] == "gemini-2.5-flash":
        judge_model = "gemini-2.5-flash-preview-05-20"
    else:
        judge_model = config_dict["judge_model"]

    stream = client.models.generate_content_stream(
        model=judge_model,
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=config_dict["temperature"],
            max_output_tokens=config_dict["max_completion_tokens"],
            thinking_config=ThinkingConfig(
                thinking_budget=config_dict["max_completion_tokens"] * 2 // 3
            ),
        ),
        contents=user_prompt,
    )

    # Aggregate streamed chunks into a response-shaped object so downstream
    # parsing (`response.text` / `response.usage_metadata`) stays unchanged.
    text_parts = []
    usage_metadata = None
    for chunk in stream:
        if chunk.text:
            text_parts.append(chunk.text)
        if chunk.usage_metadata is not None:
            usage_metadata = chunk.usage_metadata

    return SimpleNamespace(
        text="".join(text_parts),
        usage_metadata=usage_metadata or _ZERO_USAGE_METADATA,
    )
