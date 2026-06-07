"""Inference for the free-text keystroke liveness detector.

Loads the bundle produced by train_liveness.py and scores a single attempt.
Feature extraction MUST stay identical to train_liveness.extract_features
(same 16 columns, same formulas, same MIN_KEYS) or the scaler/model will see
a different distribution. See docs/keystroke-features.md.
"""
import joblib
import numpy as np

FEATURE_COLUMNS = [
    "ht_mean", "ht_std", "ht_median", "ht_min", "ht_max", "ht_cv",
    "ft_mean", "ft_std", "ft_median", "ft_min", "ft_max", "ft_cv",
    "n_keys", "total_time_ms", "typing_speed", "hesitation_ratio",
]
MIN_KEYS = 5


def _stats(a):
    mean = float(a.mean())
    std = float(a.std())
    cv = std / mean if mean else 0.0
    return mean, std, float(np.median(a)), float(a.min()), float(a.max()), cv


def features_from_timing(key_down, key_up):
    """Raw per-key timestamps (ms) -> 16-feature vector, or None if too short.

    HT[i] = key_up[i] - key_down[i]            (hold time)
    FT[i] = key_down[i] - key_down[i-1]        (down-to-down flight, i>=1)
    """
    kd = np.asarray(key_down, dtype=np.float64)
    ku = np.asarray(key_up, dtype=np.float64)
    n = min(len(kd), len(ku))
    if n < MIN_KEYS:
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
    return [
        ht_mean, ht_std, ht_med, ht_min, ht_max, ht_cv,
        ft_mean, ft_std, ft_med, ft_min, ft_max, ft_cv,
        n, total_time_ms, typing_speed, hesitation_ratio,
    ]


class LivenessDetector:
    """Wraps scaler + chosen model; returns P(synthetic) in [0, 1]."""

    def __init__(self, feature_columns, scaler, models, primary="MLP", **_):
        self.feature_columns = list(feature_columns)
        self.scaler = scaler
        self.model = models[primary]
        self.primary = primary

    def score_features(self, features):
        x = np.asarray(features, dtype=np.float64)[None, :]
        if x.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"expected {len(self.feature_columns)} features, got {x.shape[1]}")
        xs = self.scaler.transform(x)
        return float(self.model.predict_proba(xs)[0, 1])

    def score_timing(self, key_down, key_up):
        feats = features_from_timing(key_down, key_up)
        if feats is None:
            return None
        return self.score_features(feats)

    @classmethod
    def load(cls, path, primary="MLP"):
        bundle = joblib.load(path)
        return cls(primary=primary, **bundle)
