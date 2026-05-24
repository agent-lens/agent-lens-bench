from dataclasses import dataclass
from typing import Optional


EPS = 1e-9


@dataclass(frozen=True)
class RatioPolicy:
    warn_low: float
    warn_high: float
    alert_low: float
    alert_high: float


def safe_ratio(numerator: float, denominator: float) -> float:
    return (numerator + EPS) / (denominator + EPS)


def ratio_flags(
    *,
    ratio: float,
    p_value: Optional[float],
    policy: RatioPolicy,
    p_value_alpha: float = 0.05,
) -> tuple[bool, bool]:
    """Return (warning_flag, alert_flag) based on ratio thresholds and optional p-value."""

    warn = ratio < policy.warn_low or ratio > policy.warn_high
    alert = ratio < policy.alert_low or ratio > policy.alert_high

    if p_value is not None and p_value < p_value_alpha:
        alert = True
        warn = True

    return warn, alert
