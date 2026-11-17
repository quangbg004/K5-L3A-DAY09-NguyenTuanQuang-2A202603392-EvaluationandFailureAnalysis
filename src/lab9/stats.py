"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    counts = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    for expected, predicted in zip(human, judge, strict=True):
        if expected not in (POS, "PASS") or predicted not in (POS, "PASS"):
            raise ValueError("judge labels must be PASS or FAIL")
        key = ("t" if expected == predicted else "f") + ("p" if predicted == POS else "n")
        counts[key] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    counts = confusion(human, judge)
    tp = counts["tp"]
    predicted_positive = tp + counts["fp"]
    actual_positive = tp + counts["fn"]
    return (
        tp / predicted_positive if predicted_positive else 0.0,
        tp / actual_positive if actual_positive else 0.0,
    )


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """Cohen's kappa; raise ValueError if agreement by chance is 1 or data is empty."""
    counts = confusion(human, judge)
    n = sum(counts.values())
    human_fail = counts["tp"] + counts["fn"]
    judge_fail = counts["tp"] + counts["fp"]
    chance_pairs = human_fail * judge_fail + (n - human_fail) * (n - judge_fail)
    agreement_pairs = (counts["tp"] + counts["tn"]) * n
    if chance_pairs == n * n:
        raise ValueError("Cohen's kappa is undefined")
    return (agreement_pairs - chance_pairs) / (n * n - chance_pairs)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1
    if abs(denominator) < 1e-12:
        return float("nan")
    estimate = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, estimate))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    if len(a) != len(b) or len(a) == 0:
        raise ValueError("paired bootstrap requires equal, non-empty samples")
    a_values, b_values = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if not np.isfinite(a_values).all() or not np.isfinite(b_values).all():
        raise ValueError("paired bootstrap requires finite values")

    def mean_difference(pr, baseline, axis):
        return np.mean(pr - baseline, axis=axis)

    delta = float(mean_difference(a_values, b_values, axis=0))
    if np.array_equal(a_values, b_values) or len(a_values) == 1:
        return delta, delta, delta
    interval = bootstrap(
        (a_values, b_values), mean_difference, paired=True, method="percentile",
        n_resamples=n_resamples, rng=np.random.default_rng(rng), confidence_level=confidence,
    ).confidence_interval
    return delta, float(interval.low), float(interval.high)


def _validate_pass_counts(n: int, c: int, k: int) -> None:
    if any(type(value) is not int for value in (n, c, k)) or not (0 <= c <= n and 1 <= k <= n):
        raise ValueError("expected integer counts with 0 <= c <= n and 1 <= k <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_pass_counts(n, c, k)
    return (comb(n, k) - comb(n - c, k)) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_pass_counts(n, c, k)
    return comb(c, k) / comb(n, k)
