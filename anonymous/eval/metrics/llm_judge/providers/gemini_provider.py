from typing import Any, Dict

from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig


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

    response = client.models.generate_content(
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
    return response
