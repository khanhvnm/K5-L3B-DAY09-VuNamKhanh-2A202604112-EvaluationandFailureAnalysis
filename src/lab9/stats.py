"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge sequences must have the same length")
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        h = h.strip().upper()
        j = j.strip().upper()
        if h == "FAIL" and j == "FAIL":
            counts["tp"] += 1
        elif h == "PASS" and j == "FAIL":
            counts["fp"] += 1
        elif h == "FAIL" and j == "PASS":
            counts["fn"] += 1
        elif h == "PASS" and j == "PASS":
            counts["tn"] += 1
        else:
            raise ValueError(f"labels must be PASS or FAIL, got human={h!r}, judge={j!r}")
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    if len(human) != len(judge):
        raise ValueError("human and judge sequences must have the same length")
    h = [x.strip().upper() for x in human]
    j = [x.strip().upper() for x in judge]
    if not h:
        raise ValueError("cannot calculate kappa for an empty sequence")
    n = len(h)
    if any(x not in {"PASS", "FAIL"} for x in h + j):
        raise ValueError("labels must be PASS or FAIL")
    observed = sum(human_label == judge_label for human_label, judge_label in zip(h, j)) / n
    expected = (
        sum(h.count(label) / n * j.count(label) / n
            for label in ("PASS", "FAIL"))
    )
    if 1 - expected == 0:
        raise ValueError("kappa is undefined when expected agreement is 1")
    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1
    if denominator == 0:
        return 0.0
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("a and b must contain the same number of paired items")
    if len(a) == 0:
        raise ValueError("cannot bootstrap empty sequences")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    if not np.all(np.isfinite(a_arr)) or not np.all(np.isfinite(b_arr)):
        raise ValueError("bootstrap inputs must be finite")
    differences = a_arr - b_arr
    if np.all(differences == 0):
        return 0.0, 0.0, 0.0

    def statistic(a_values: np.ndarray, b_values: np.ndarray) -> float:
        return float(np.mean(a_values - b_values))

    result = bootstrap(
        (a_arr, b_arr),
        statistic,
        paired=True,
        vectorized=False,
        method="percentile",
        n_resamples=n_resamples,
        confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    mean_diff = float(np.mean(differences))
    lo = float(result.confidence_interval.low)
    hi = float(result.confidence_interval.high)
    return mean_diff, lo, hi


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    for value in (n, c, k):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("n, c, and k must be integers")
    if n < 0 or c < 0 or k < 0:
        raise ValueError("n, c, and k must be non-negative")
    if c > n:
        raise ValueError("c cannot exceed n")
    if k > n:
        raise ValueError("k cannot exceed n")
    if k == 0:
        return 0.0
    if n == 0:
        return 0.0
    failing = n - c
    return 1.0 - math.comb(failing, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    for value in (n, c, k):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("n, c, and k must be integers")
    if n < 0 or c < 0 or k < 0:
        raise ValueError("n, c, and k must be non-negative")
    if c > n:
        raise ValueError("c cannot exceed n")
    if k > n:
        raise ValueError("k cannot exceed n")
    if k == 0:
        return 1.0
    if n == 0:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)
