"""Train keystroke liveness detectors (human vs machine-synthesized) on the
free-text Mendeley dataset under data/.

Feature spec: see docs/keystroke-features.md (24 aggregate timing features with
--extra-features).
Label: HUMAN -> 0, *Synthesizer -> 1 (risk = P(synthetic)).
Split: grouped by subject so the same person never appears in both train/test.
"""
import argparse
import glob
import os
import random
import statistics
import time

import joblib
import numpy as np
from sklearn.ensemble import (HistGradientBoostingClassifier, IsolationForest,
                              RandomForestClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "ht_mean", "ht_std", "ht_median", "ht_min", "ht_max", "ht_cv",
    "ft_mean", "ft_std", "ft_median", "ft_min", "ft_max", "ft_cv",
    "n_keys", "total_time_ms", "typing_speed", "hesitation_ratio",
]
MIN_KEYS = 5


def _stats(a):
    """mean, std(pop), median, min, max, cv for a 1-D float array."""
    mean = float(a.mean())
    std = float(a.std())  # population std, matches statistics.pstdev
    cv = std / mean if mean else 0.0
    return mean, std, float(np.median(a)), float(a.min()), float(a.max()), cv


EXTRA_COLUMNS = [
    "ht_p25", "ht_p75", "ht_iqr", "ft_p25", "ft_p75", "ft_iqr",
    "ft_fast_ratio", "ht_ft_ratio",
]
# mixed-length training: each window is a random length in this range, so the
# model is length-agnostic instead of betting on one login length.
MIXED_MIN, MIXED_MAX = 12, 40


def _compute(ht, ft, extra=False):
    """Feature vector from hold-time array (ht) and within-sequence
    down-to-down flight array (ft, no -1). Mirrors inference.features_from_timing.
    extra=True appends EXTRA_COLUMNS (experimental, see keystroke-experiments.md)."""
    ht_mean, ht_std, ht_med, ht_min, ht_max, ht_cv = _stats(ht)
    ft_mean, ft_std, ft_med, ft_min, ft_max, ft_cv = _stats(ft)
    n_keys = len(ht)
    total_time_ms = float(ft.sum() + ht[-1])
    typing_speed = n_keys / (total_time_ms / 1000.0) if total_time_ms > 0 else 0.0
    hesitation_ratio = float((ft > 2 * ft_med).sum()) / n_keys if ft_med > 0 else 0.0
    vec = [
        ht_mean, ht_std, ht_med, ht_min, ht_max, ht_cv,
        ft_mean, ft_std, ft_med, ft_min, ft_max, ft_cv,
        n_keys, total_time_ms, typing_speed, hesitation_ratio,
    ]
    if extra:
        ht_p25, ht_p75 = float(np.percentile(ht, 25)), float(np.percentile(ht, 75))
        ft_p25, ft_p75 = float(np.percentile(ft, 25)), float(np.percentile(ft, 75))
        ft_fast_ratio = float((ft < 50).sum()) / len(ft)   # rollover/overlap share
        ht_ft_ratio = ht_mean / ft_mean if ft_mean else 0.0
        vec += [ht_p25, ht_p75, ht_p75 - ht_p25, ft_p25, ft_p75,
                ft_p75 - ft_p25, ft_fast_ratio, ht_ft_ratio]
    return vec


def _read_htft(path):
    """Parse one CSV (VK,HT,FT) -> (ht_all, ft_col) arrays; ft_col keeps -1 sentinels."""
    ht, ftc = [], []
    with open(path, "r", newline="") as f:
        next(f, None)  # header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != 3:
                continue
            try:
                ht.append(float(parts[1]))
                ftc.append(float(parts[2]))
            except ValueError:
                continue
    return np.asarray(ht), np.asarray(ftc)


def iter_feature_vectors(path, window=0, extra=False, rng=None):
    """Yield feature vectors for one CSV.

    window=0      : one vector over the whole session.
    window="mixed": variable-length blocks (random in [MIXED_MIN, MIXED_MAX]) so
                    the model is length-agnostic.
    window=N>0    : one vector per non-overlapping block of N keys.
    Each block is treated like an independent short login (flights = within-block
    down-to-downs only), mirroring how inference sees a fresh attempt.
    """
    ht_all, ft_col = _read_htft(path)
    n = len(ht_all)
    if n < MIN_KEYS:
        return

    def block(s, w):
        ht = ht_all[s:s + w]
        ftw = ft_col[s + 1:s + w]           # within-block down-to-downs
        ftw = ftw[ftw != -1]
        if len(ht) >= MIN_KEYS and ftw.size:
            return _compute(ht, ftw, extra)
        return None

    if window == "mixed":
        r = rng or random
        s = 0
        while s < n:
            w = r.randint(MIXED_MIN, MIXED_MAX)
            if s + w > n:
                break
            v = block(s, w)
            if v is not None:
                yield v
            s += w
        return
    if window <= 0:
        ft = ft_col[ft_col != -1]
        if ft.size:
            yield _compute(ht_all, ft, extra)
        return
    for s in range(0, n - window + 1, window):
        v = block(s, window)
        if v is not None:
            yield v


KNOWLEDGE_LEVELS = [
    "BetweenSubject", "WithinSubject100", "WithinSubject500",
    "WithinSubject2500", "WithinSubjectAll",
]


def parse_variant(path):
    """Return (knowledge, synthesizer) for a synth file, or ('HUMAN','HUMAN')."""
    name = os.path.basename(path)[:-4]  # drop .csv
    if name.endswith("HUMAN"):
        return "HUMAN", "HUMAN"
    # {CORPUS}-{SUBJECT}-{SESSION}-{KNOWLEDGE}-{SYNTHESIZER}
    parts = name.rsplit("-", 2)
    return parts[-2], parts[-1]


def build_dataset(data_dir, corpora, synth_per_session, max_subjects, seed,
                  window=0, max_windows=0, extra=False):
    rng = random.Random(seed)
    X, y, groups, meta = [], [], [], []
    n_skipped = 0
    for corpus in corpora:
        subjects = sorted(os.listdir(os.path.join(data_dir, corpus)))
        if max_subjects:
            subjects = subjects[:max_subjects]
        for subj in subjects:
            sdir = os.path.join(data_dir, corpus, subj)
            if not os.path.isdir(sdir):
                continue
            gid = f"{corpus}/{subj}"
            humans = glob.glob(os.path.join(sdir, "*HUMAN.csv"))
            synths = glob.glob(os.path.join(sdir, "*Synthesizer.csv"))
            # balance: per subject, sample synth_per_session * (#human) synth files
            k = min(len(synths), synth_per_session * max(len(humans), 1))
            chosen = humans + rng.sample(synths, k)
            for path in chosen:
                label = 0 if path.endswith("HUMAN.csv") else 1
                lvl = parse_variant(path)[0]
                vecs = list(iter_feature_vectors(path, window, extra, rng))
                if not vecs:
                    n_skipped += 1
                    continue
                if max_windows and len(vecs) > max_windows:
                    vecs = rng.sample(vecs, max_windows)
                for feat in vecs:
                    X.append(feat)
                    y.append(label)
                    groups.append(gid)
                    meta.append(lvl)
    return (np.asarray(X), np.asarray(y), np.asarray(groups),
            np.asarray(meta), n_skipped)


def far_frr(y_true, y_pred):
    # FAR: synth(1) accepted as human(0); FRR: human(0) rejected as synth(1)
    synth = y_true == 1
    human = y_true == 0
    far = float((y_pred[synth] == 0).mean()) if synth.any() else 0.0
    frr = float((y_pred[human] == 1).mean()) if human.any() else 0.0
    return far, frr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--corpora", default="GAY,GUN,REVIEW,LSIA")
    ap.add_argument("--synth-per-session", type=int, default=2)
    ap.add_argument("--max-subjects", type=int, default=0, help="0 = all")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--window", default="0",
                    help="0 = whole session; N = per N-key block; 'mixed' = "
                         "random-length blocks (login-length-agnostic)")
    ap.add_argument("--max-windows", type=int, default=0,
                    help="cap windows sampled per file (0 = no cap)")
    ap.add_argument("--min-keys", type=int, default=10,
                    help="deployment floor: below this, inference returns "
                         "insufficient_keystroke instead of scoring")
    ap.add_argument("--extra-features", action="store_true",
                    help="append EXTRA_COLUMNS (experimental)")
    ap.add_argument("--save-only", default="",
                    help="save only this model in the bundle (e.g. HistGradientBoosting)")
    ap.add_argument("--out", default="services/keystroke-ml/liveness_detector.joblib")
    args = ap.parse_args()

    corpora = [c.strip() for c in args.corpora.split(",") if c.strip()]
    window = args.window if args.window == "mixed" else int(args.window)
    print(f"corpora={corpora} synth_per_session={args.synth_per_session} "
          f"max_subjects={args.max_subjects or 'all'} window={window or 'full'} "
          f"max_windows={args.max_windows or 'all'} min_keys={args.min_keys}")

    t0 = time.time()
    X, y, groups, meta, n_skipped = build_dataset(
        args.data_dir, corpora, args.synth_per_session, args.max_subjects,
        args.seed, window, args.max_windows, args.extra_features)
    print(f"loaded {len(X)} samples (human={int((y==0).sum())} synth={int((y==1).sum())}) "
          f"skipped={n_skipped} subjects={len(set(groups))} in {time.time()-t0:.1f}s")

    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=args.seed)
    tr, te = next(gss.split(X, y, groups))
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
    meta_te = meta[te]
    print(f"train={len(tr)} test={len(te)} (split by subject)")

    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)

    models = {
        "LogisticRegression": LogisticRegression(
            max_iter=1000, class_weight="balanced"),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, class_weight="balanced", n_jobs=-1,
            random_state=args.seed),
        "MLP": MLPClassifier(
            hidden_layer_sizes=(32, 16), max_iter=300, random_state=args.seed),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=500, learning_rate=0.1, max_leaf_nodes=63,
            random_state=args.seed),
    }

    trained, results, probas = {}, [], {}
    for name, model in models.items():
        t = time.time()
        model.fit(Xtr_s, ytr)
        proba = model.predict_proba(Xte_s)[:, 1]
        pred = (proba >= 0.5).astype(int)
        auc = roc_auc_score(yte, proba)
        acc = float((pred == yte).mean())
        far, frr = far_frr(yte, pred)
        results.append((name, auc, acc, far, frr, time.time() - t))
        trained[name] = model
        probas[name] = proba

    # one-class baseline: IsolationForest trained on HUMAN only
    t = time.time()
    iso = IsolationForest(n_estimators=200, random_state=args.seed, n_jobs=-1)
    iso.fit(Xtr_s[ytr == 0])
    iso_score = -iso.score_samples(Xte_s)  # higher = more anomalous = more synth
    auc = roc_auc_score(yte, iso_score)
    iso_pred = (iso.predict(Xte_s) == -1).astype(int)
    acc = float((iso_pred == yte).mean())
    far, frr = far_frr(yte, iso_pred)
    results.append(("IsolationForest(1-class)", auc, acc, far, frr, time.time() - t))
    trained["IsolationForest"] = iso
    # normalize iso anomaly score to [0,1] so 0.5 threshold is comparable-ish
    probas["IsolationForest"] = (iso_score - iso_score.min()) / (
        np.ptp(iso_score) or 1.0)

    print("\nmodel                       AUC     ACC     FAR     FRR    fit(s)")
    print("-" * 64)
    for name, auc, acc, far, frr, dt in sorted(results, key=lambda r: -r[1]):
        print(f"{name:26s} {auc:.4f}  {acc:.4f}  {far:.4f}  {frr:.4f}  {dt:6.1f}")

    # ---- breakdown by attacker knowledge level (the honest test) ----
    # FAR per level = fraction of THAT attack type that slips through (pred=human)
    human_mask = meta_te == "HUMAN"
    print("\nFAR by attacker knowledge level (lower = better; "
          "WithinSubjectAll = strongest attacker):")
    header = "level               n   " + "  ".join(f"{n[:10]:>10s}" for n in probas)
    print(header)
    print("-" * len(header))
    for lvl in KNOWLEDGE_LEVELS:
        lvl_mask = meta_te == lvl
        n = int(lvl_mask.sum())
        if n == 0:
            continue
        cells = []
        for name, proba in probas.items():
            far_lvl = float((proba[lvl_mask] < 0.5).mean())  # attack passed as human
            cells.append(f"{far_lvl:10.4f}")
        print(f"{lvl:18s} {n:5d}  " + "  ".join(cells))
    # per-level AUC for the best model (humans vs that level only)
    best = max(results, key=lambda r: r[1])[0]
    print(f"\nAUC by knowledge level for best model ({best}):")
    for lvl in KNOWLEDGE_LEVELS:
        lvl_mask = meta_te == lvl
        if lvl_mask.sum() == 0:
            continue
        sub = human_mask | lvl_mask
        auc_lvl = roc_auc_score(yte[sub], probas[best][sub])
        print(f"  {lvl:18s} AUC={auc_lvl:.4f}  (n_attack={int(lvl_mask.sum())})")

    saved_models = ({args.save_only: trained[args.save_only]}
                    if args.save_only else trained)
    bundle = {
        "feature_columns": FEATURE_COLUMNS + (EXTRA_COLUMNS if args.extra_features else []),
        "min_keys": args.min_keys,
        "scaler": scaler,
        "models": saved_models,
        "metrics": {r[0]: {"auc": r[1], "acc": r[2], "far": r[3], "frr": r[4]}
                    for r in results},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    joblib.dump(bundle, args.out)
    print(f"\nsaved -> {args.out}  ({os.path.getsize(args.out)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
