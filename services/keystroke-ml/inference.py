"""Inference for the free-text keystroke liveness detector.

Loads the bundle produced by train_liveness.py and scores a single attempt.
Feature extraction MUST stay identical to train_liveness._compute(..., extra=True)
(same 24 columns and formulas) or the scaler/model will see
a different distribution. See docs/keystroke-features.md.
"""
import joblib
import numpy as np

FEATURE_COLUMNS = [
    "ht_mean", "ht_std", "ht_median", "ht_min", "ht_max", "ht_cv",
    "ft_mean", "ft_std", "ft_median", "ft_min", "ft_max", "ft_cv",
    "n_keys", "total_time_ms", "typing_speed", "hesitation_ratio",
    # extra (see docs/keystroke-experiments.md)
    "ht_p25", "ht_p75", "ht_iqr", "ft_p25", "ft_p75", "ft_iqr",
    "ft_fast_ratio", "ht_ft_ratio",
]
# deployment floor: below this many keys we don't score (return None -> the
# service treats it as insufficient_keystroke). The trained model is
# length-agnostic (mixed-length windows), so this is a small statistical floor,
# not a bet on real login length. Overridden by the bundle's saved min_keys.
DEFAULT_MIN_KEYS = 10


def _stats(a):
    mean = float(a.mean())
    std = float(a.std())
    cv = std / mean if mean else 0.0
    return mean, std, float(np.median(a)), float(a.min()), float(a.max()), cv


def features_from_timing(key_down, key_up, min_keys=DEFAULT_MIN_KEYS):
    """Raw per-key timestamps (ms) -> 24-feature vector, or None if too short.

    Must stay identical to train_liveness._compute(..., extra=True).
    HT[i] = key_up[i] - key_down[i]            (hold time)
    FT[i] = key_down[i] - key_down[i-1]        (down-to-down flight, i>=1)
    """
    kd = np.asarray(key_down, dtype=np.float64)
    ku = np.asarray(key_up, dtype=np.float64)
    n = min(len(kd), len(ku))
    if n < min_keys:
        return None
    kd, ku = kd[:n], ku[:n]
    ht = ku - kd
    ft = np.diff(kd)  # length n-1, first-key sentinel naturally excluded
    if ft.size == 0:
        return None
    ht_mean, ht_std, ht_med, ht_min, ht_max, ht_cv = _stats(ht)
    ft_mean, ft_std, ft_med, ft_min, ft_max, ft_cv = _stats(ft)
    total_time_ms = float(ft.sum() + ht[-1])
    typing_speed = n / (total_time_ms / 1000.0) if total_time_ms > 0 else 0.0
    hesitation_ratio = float((ft > 2 * ft_med).sum()) / n if ft_med > 0 else 0.0
    ht_p25, ht_p75 = float(np.percentile(ht, 25)), float(np.percentile(ht, 75))
    ft_p25, ft_p75 = float(np.percentile(ft, 25)), float(np.percentile(ft, 75))
    ft_fast_ratio = float((ft < 50).sum()) / ft.size
    ht_ft_ratio = ht_mean / ft_mean if ft_mean else 0.0
    return [
        ht_mean, ht_std, ht_med, ht_min, ht_max, ht_cv,
        ft_mean, ft_std, ft_med, ft_min, ft_max, ft_cv,
        n, total_time_ms, typing_speed, hesitation_ratio,
        ht_p25, ht_p75, ht_p75 - ht_p25, ft_p25, ft_p75, ft_p75 - ft_p25,
        ft_fast_ratio, ht_ft_ratio,
    ]


class LivenessDetector:
    """Wraps scaler + chosen model; returns P(synthetic) in [0, 1]."""

    def __init__(self, feature_columns, scaler, models, min_keys=DEFAULT_MIN_KEYS,
                 primary="HistGradientBoosting", **_):
        self.feature_columns = list(feature_columns)
        self.scaler = scaler
        self.model = models[primary]
        self.primary = primary
        self.min_keys = min_keys

    def score_features(self, features):
        x = np.asarray(features, dtype=np.float64)[None, :]
        if x.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"expected {len(self.feature_columns)} features, got {x.shape[1]}")
        xs = self.scaler.transform(x)
        return float(self.model.predict_proba(xs)[0, 1])

    def score_timing(self, key_down, key_up):
        feats = features_from_timing(key_down, key_up, self.min_keys)
        if feats is None:
            return None
        return self.score_features(feats)

    @classmethod
    def load(cls, path, primary="HistGradientBoosting"):
        bundle = joblib.load(path)
        # fall back to the only model present if the preferred one is absent
        if primary not in bundle.get("models", {}):
            primary = next(iter(bundle["models"]))
        return cls(primary=primary, **bundle)
