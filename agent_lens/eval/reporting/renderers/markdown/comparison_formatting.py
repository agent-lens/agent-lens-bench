"""Small formatting helpers used by comparison Markdown renderer."""

from typing import Any, Optional


def bool_flag(label: str, value: Optional[bool]) -> str:
    """Render boolean flags; highlight only top-level ``alert: YES`` a bit."""

    is_general_alert = label.lower() == "alert"

    if value is True and is_general_alert:
        # Muted red just for the word YES, rest of the line stays normal.
        return f"- {label}: <span style='color: #c22; font-weight: bold'>YES</span>"

    if value is True:
        return f"- {label}: YES"
    if value is False:
        return f"- {label}: no"
    return f"- {label}: n/a"


def fmt_alert_cell(value: Optional[bool]) -> str:
    """Render alert cell value for Markdown tables.

    Make all YES alerts red.
    """

    if value is True:
        return "<span style='color: #c22; font-weight: bold'>YES</span>"
    if value is False:
        return "no"
    return "n/a"


def fmt_bool(v: Optional[bool]) -> str:
    if v is True:
        return "YES"
    if v is False:
        return "no"
    return "n/a"


def fmt_val(v: Any) -> str:
    return "`{}`".format(v) if v is not None else "--"
