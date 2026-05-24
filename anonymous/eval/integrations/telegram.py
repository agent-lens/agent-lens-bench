import logging
import os

import tqdm

from anonymous.eval.integrations.http import post_json_with_retries

from anonymous.eval.comparison.compute.models import AlertInfo

LOG = logging.getLogger(__name__)

_ENV_BENCHMARK_TELEGRAM_BOT_TOKEN = "BENCHMARK_TELEGRAM_BOT_TOKEN"
_ENV_BENCHMARK_TELEGRAM_BOT_CHAT_ID = "BENCHMARK_TELEGRAM_BOT_CHAT_ID"
_ENV_BENCHMARK_TELEGRAM_BOT_MSG_THREAD_ID = "BENCHMARK_TELEGRAM_BOT_MSG_THREAD_ID"

_ST_EXPANDABLE_BLOCKQUOTE = "<blockquote expandable>"
_END_EXPANDABLE_BLOCKQUOTE = "</blockquote>"

_GH_ASSIGNEE_ENV = "BENCHMARK_TELEGRAM_BOT_ASSIGNEE"


def _split_into_chunks(s: str, max_chars: int = 4096):
    max_chars = (
        max_chars - len(_ST_EXPANDABLE_BLOCKQUOTE) - len(_END_EXPANDABLE_BLOCKQUOTE)
    )
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    parts = []
    i = 0
    n = len(s)
    while i < n:
        cut = min(i + max_chars, n)
        part = s[i:cut]
        if i != 0:
            part = _ST_EXPANDABLE_BLOCKQUOTE + part
        if cut != n:
            part = part + "\n" + _END_EXPANDABLE_BLOCKQUOTE
        parts.append(part)
        i = cut
    return parts


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def compose_body(alert_info: AlertInfo, tldr: str) -> str:
    parts = [
        f"{_ST_EXPANDABLE_BLOCKQUOTE}TL;DR: {escape_html(tldr)}{_END_EXPANDABLE_BLOCKQUOTE}\n"
    ]
    if alert_info.alerts:
        parts.append(
            f"{_ST_EXPANDABLE_BLOCKQUOTE}ALERTS (run1 vs run2):\n- "
            + escape_html("\n- ".join(alert_info.alerts))
            + _END_EXPANDABLE_BLOCKQUOTE
        )
    if alert_info.warnings:
        parts.append(
            f"\n{_ST_EXPANDABLE_BLOCKQUOTE}WARNINGS (run1 vs run2):\n- "
            + escape_html("\n- ".join(alert_info.warnings))
            + _END_EXPANDABLE_BLOCKQUOTE
        )
    if not parts:
        parts.append("No alerts or warnings.")
    return "\n\n".join(parts)


def get_nightly_assignee_mention():
    assignee = os.getenv(_GH_ASSIGNEE_ENV, None)
    if assignee is None:
        return f"Not specified @-name or user_id (see `{_GH_ASSIGNEE_ENV}` GitHub env)"

    if assignee.startswith("@"):
        return assignee

    if assignee.startswith('<a href="tg://user?id=') and assignee.endswith("</a>"):
        return assignee

    if assignee.isdigit():
        return f'<a href="tg://user?id={assignee}">Unknown Sentry</a>'

    LOG.warning("Unknown alerting assignee format: %s", assignee)
    return assignee


def send_alerts(
    alerts: AlertInfo,
    tldr: str,
    bench_tag_name: str,
    language: str,
    sbs_name: str,
    tracking_url: str | None,
    github_action_run_url: str | None,
    retries: int = 1,
) -> None:
    if len(alerts.alerts) == 0:
        LOG.info("No alerts; nothing to send.")
        return

    message = f"Bench tag: {bench_tag_name}\nLanguage: {language}\n"
    if tracking_url is not None:
        message += f"Tracking run: {sbs_name}\nTracking link: {tracking_url}\n"
    if github_action_run_url is not None:
        message += f"Github run: {github_action_run_url}\n"

    message += compose_body(alerts, tldr)

    current_assignee = get_nightly_assignee_mention()
    message = f"⚠️Benchmark alerts\nAssignee: {current_assignee}\n{message}"

    LOG.info(message)

    token = os.getenv(_ENV_BENCHMARK_TELEGRAM_BOT_TOKEN)
    chat_id = os.getenv(_ENV_BENCHMARK_TELEGRAM_BOT_CHAT_ID)
    msg_thread_id = os.getenv(_ENV_BENCHMARK_TELEGRAM_BOT_MSG_THREAD_ID, "")

    if token is None:
        LOG.error("%s is none", _ENV_BENCHMARK_TELEGRAM_BOT_TOKEN)
        return

    if chat_id is None:
        LOG.error("%s is none", _ENV_BENCHMARK_TELEGRAM_BOT_CHAT_ID)
        return

    do_send(chat_id, msg_thread_id, message, retries, token)


_TELEGRAM_HTTP_TIMEOUT_S = 15.0


def do_send(chat_id: str, msg_thread_id: str, message: str, retries: int, token: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    parts = _split_into_chunks(message, max_chars=4096)

    for part in tqdm.tqdm(parts):
        payload = {
            "chat_id": chat_id,
            "message_thread_id": msg_thread_id,
            "text": part,
            "parse_mode": "HTML",
        }

        response = post_json_with_retries(
            url=url,
            payload=payload,
            retries=retries,
            timeout_s=_TELEGRAM_HTTP_TIMEOUT_S,
            logger=LOG,
        )

        if response is None or not response.ok:
            LOG.error(
                "Failed to send part of the message after %d attempts. Response: %s",
                max(1, retries + 1),
                response,
            )
