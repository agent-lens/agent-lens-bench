from typing import Any, Mapping

DEFAULT_REVIEW_LANGUAGE = "English"
DEFAULT_REVIEW_TIMEZONE = "Europe/London"


def get_review_style_config(config_dict: Mapping[str, Any]) -> Mapping[str, Any]:
    review_style = config_dict.get("review_style", {})
    return review_style if isinstance(review_style, Mapping) else {}


def get_review_language(config_dict: Mapping[str, Any]) -> str:
    review_style = get_review_style_config(config_dict)
    language = str(review_style.get("language", "")).strip()
    return language or DEFAULT_REVIEW_LANGUAGE


def get_review_timezone(config_dict: Mapping[str, Any]) -> str:
    review_style = get_review_style_config(config_dict)
    timezone = str(review_style.get("timezone", "")).strip()
    return timezone or DEFAULT_REVIEW_TIMEZONE


def get_answer_language_instruction(config_dict: Mapping[str, Any]) -> str:
    language = get_review_language(config_dict)
    return f"Answer in {language}."


def get_user_specific_prompt_instruction(config_dict: Mapping[str, Any]) -> str:
    review_style = get_review_style_config(config_dict)
    user_text = str(review_style.get("user_specific_style_prompt", "")).strip()
    if user_text != "":
        return f"Important instruction from end-user:\n<end-user>\n{user_text}\n</end-user>\n"
    else:
        return ""
