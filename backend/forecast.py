"""!!! STUB !!! Teammate owns the real forecast model; replace this whole file.

prob_above(location, threshold_f, date) -> P(daily high >= threshold_f), 0 to 1.

The stub assumes the daily high is normally distributed around a fixed, made-up
mean, so probabilities are consistent across thresholds (P(>=60) > P(>=70))
and equal 0.5 at the mean. The mean wobbles slightly on each call so the
market maker's quotes visibly move in the demo. Location and date are ignored.
"""
import math
import random

STUB_MEAN_F = 66.0  # made-up forecast high
STUB_SD_F = 5.0     # made-up forecast uncertainty
STUB_JITTER_F = 0.3


def prob_above(location: str, threshold_f: float, date: str) -> float:
    mean = STUB_MEAN_F + random.uniform(-STUB_JITTER_F, STUB_JITTER_F)
    z = (threshold_f - mean) / STUB_SD_F
    return 0.5 * math.erfc(z / math.sqrt(2))  # 1 - normal CDF
