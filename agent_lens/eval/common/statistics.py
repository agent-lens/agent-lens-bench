from functools import lru_cache
from typing import Any, List, Union

import numpy as np
from scipy.stats import mannwhitneyu, multinomial


@lru_cache(maxsize=10000)
def _cached_multinomial_pmf(win, tie, loss, num, p_win, p_tie, p_loss):
    """Cached multinomial PMF computation to avoid redundant calculations."""
    return multinomial.pmf([win, tie, loss], num, [p_win, p_tie, p_loss])


def conservative_trinomial_test(w_obs, t_obs, l_obs):
    """
    Conducts a trinomial test for outcomes: wins, ties, and losses for multiple nuisance parameter values (llm-judge tie prob),
    takes maximum as a higher bound estimate. Effectively, estimates p-value against indifference
    by taking max over p-values against indifference with fixed tie probs across multiple tie probs (tie prob according to llm-judge).

    Parameters:
      w_obs (int): Observed number of wins.
      t_obs (int): Observed number of ties.
      l_obs (int): Observed number of losses.

    Returns:
      p_value (float): Conservative estimation of one-sided p-value based on statistic, see compute_stat.
    """
    num_matches = w_obs + t_obs + l_obs
    if num_matches > 500:  # Threshold for performance reasons
        return -1

    def compute_stat(wins, ties, losses, prob_tie):
        return wins - losses + np.abs(prob_tie * num_matches - ties) / 4

    # Iterate over null hypotheses with varying tie probability
    p_values = []
    for p_tie in np.linspace(0.05, 0.95, num=10):
        # Under the null hypothesis:
        p_win = (1 - p_tie) / 2
        p_loss = p_win
        # Observed test statistic
        stat_obs = compute_stat(w_obs, t_obs, l_obs, p_tie)
        p_value = 0.0
        for tie in range(num_matches + 1):
            for win in range(num_matches - tie + 1):
                loss = num_matches - tie - win
                stat_here = compute_stat(win, tie, loss, p_tie)
                if stat_here >= stat_obs:
                    outcome_prob = _cached_multinomial_pmf(
                        win, tie, loss, num_matches, p_win, p_tie, p_loss
                    )
                    p_value += outcome_prob
        p_values.append(p_value)
    return max(p_values)


def paired_permutation_test(
    scores: List[float],
    *,
    alternative: str = "two-sided",
    max_exact_n: int = 17,
    num_random: int = 100000,
    seed: int = 42,
    round_to: int = 3,
) -> float:
    """Paired permutation (randomization) test against indifference.

    Treats each `scores[i]` as a paired difference (Agent2 - Agent1) for the same task.
    Under the null, flipping the sign of each paired difference is exchangeable.

    Returns a p-value for the mean statistic.

    Notes:
    - If `len(scores) == 0`, returns 1.0 (caller can still wrap to None if desired).
    - Uses exact enumeration for `n <= max_exact_n`, else Monte Carlo with `num_random` samples.
    """

    scores = [float(s) for s in scores if s is not None]
    n = len(scores)
    if n == 0:
        return 1.0

    if alternative not in {"two-sided", "greater", "less"}:
        raise ValueError(f"Unexpected alternative: {alternative}")

    obs = float(np.mean(scores))

    def is_extreme(stat: float) -> bool:
        if alternative == "two-sided":
            return abs(stat) >= abs(obs)
        if alternative == "greater":
            return stat >= obs
        return stat <= obs

    if n <= max_exact_n:
        # Exact: iterate over all 2^n sign-flips
        extreme = 0
        total = 1 << n
        for mask in range(total):
            flipped = [(-scores[i] if (mask >> i) & 1 else scores[i]) for i in range(n)]
            mean_diff_perm = float(np.mean(flipped))
            if is_extreme(mean_diff_perm):
                extreme += 1
        # add-one smoothing
        p_value = (extreme + 1) / (total + 1)
        return round(float(p_value), round_to)

    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(num_random, n))
    stats = np.mean(signs * np.asarray(scores)[None, :], axis=1)
    extreme = int(np.sum([is_extreme(float(s)) for s in stats]))
    p_value = (extreme + 1) / (num_random + 1)
    return round(float(p_value), round_to)


def safe_mannwhitneyu(
    x: List[float],
    y: List[float],
    *,
    alternative: str = "two-sided",
    round_to: int = 4,
) -> float:
    """Mann–Whitney U test p-value with empty-list handling."""
    if len(x) == 0 or len(y) == 0:
        return 1.0
    return round(float(mannwhitneyu(x, y, alternative=alternative)[1]), round_to)


def safe_mean(
    x: List[float],
    *,
    ret_val: Union[Any, None] = -10000.0,
    round_to: int = 4,
) -> float:
    """Mean with empty-list handling (compatible with the old test_plugin helper)."""
    if len(x) == 0:
        return ret_val
    return round(float(np.mean(x).item()), round_to)
