from typing import Any, Dict

import anthropic


# noinspection PyTypeChecker
def get_anthropic_response(
    config_dict: Dict, system_prompt: str, user_prompt: str, api_key: str
) -> Any:
    client = anthropic.Anthropic(api_key=api_key)

    with client.messages.stream(
        model=config_dict["judge_model"],
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=config_dict["max_completion_tokens"],
        # temperature=config_dict['temperature'],
        system=system_prompt,
        thinking={"type": "adaptive"},
        extra_body={"output_config": {"effort": config_dict["reasoning_effort"]}},
    ) as stream:
        return stream.get_final_message()
