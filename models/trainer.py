"""Model training and evaluation. Run:  python -m models.trainer
Artifacts (joblib + metrics.json) are written to config.settings.model_dir()."""
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, confusion_matrix, classification_report, f1_score,
                             mean_absolute_error, r2_score, silhouette_score)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import settings
from database import repository as repo
from models.features import CAT_FEATURES, NUM_FEATURES, SEG_FEATURES, build_student_features, build_subject_features

FILES = {"reg": "performance_regressor.joblib", "clf": "performance_classifier.joblib",
         "seg": "segmentation.joblib", "metrics": "metrics.json"}


def _prep():
    return ColumnTransformer([("num", SimpleImputer(strategy="median"), NUM_FEATURES),
                              ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES)])


def _rf_reg():
    return Pipeline([("prep", _prep()), ("model", RandomForestRegressor(
        n_estimators=300, min_samples_leaf=3, random_state=settings.RANDOM_STATE, n_jobs=-1))])


def _rf_clf():
    return Pipeline([("prep", _prep()), ("model", RandomForestClassifier(
        n_estimators=300, min_samples_leaf=3, class_weight="balanced", random_state=settings.RANDOM_STATE, n_jobs=-1))])


def segment_names(centers: np.ndarray) -> dict[int, str]:
    """Name clusters from centroids (scaled space): score axis vs. engagement axis."""
    idx = {f: i for i, f in enumerate(SEG_FEATURES)}
    eng_cols = [idx[f] for f in ("minutes_per_week", "active_days_ratio", "completion_rate", "quizzes_per_week")]
    names, seen = {}, {}
    for k, c in enumerate(centers):
        s, e = c[idx["avg_score"]], c[eng_cols].mean()
        if s >= 0.4:
            n = "High Achievers" if e >= 0 else "Efficient Learners"
        elif s <= -0.4:
            n = "High-Effort Strugglers" if e >= 0 else "Disengaged / At Risk"
        else:
            n = "Engaged Steady Learners" if e >= 0.4 else "Steady Learners"
        seen[n] = seen.get(n, 0) + 1
        names[k] = n if seen[n] == 1 else f"{n} ({seen[n]})"
    return names


def train_all() -> dict:
    quizzes, acts, students = repo.get_quizzes(), repo.get_activities(), repo.list_students().rename(columns={"student_id": "id"})
    data = build_subject_features(quizzes, acts, students, mode="train")
    if len(data) < 100 or data["student_id"].nunique() < 30:
        raise ValueError(f"Not enough data to train reliably ({len(data)} rows, {data['student_id'].nunique()} students).")
    X, y = data[NUM_FEATURES + CAT_FEATURES], data["target_score"]
    y_cls = y.map(settings.categorize)
    groups = data["student_id"]
    # split BY STUDENT so no student appears in both train and test
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=settings.RANDOM_STATE).split(X, y, groups))
    reg, clf = _rf_reg().fit(X.iloc[tr], y.iloc[tr]), _rf_clf().fit(X.iloc[tr], y_cls.iloc[tr])
    pred = reg.predict(X.iloc[te])
    cv = cross_val_score(_rf_reg(), X.iloc[tr], y.iloc[tr], cv=GroupKFold(5), groups=groups.iloc[tr],
                         scoring="neg_mean_absolute_error")
    cls_pred = clf.predict(X.iloc[te])
    cm = confusion_matrix(y_cls.iloc[te], cls_pred, labels=settings.CATEGORIES)
    majority = y_cls.iloc[tr].mode()[0]
    names = reg.named_steps["prep"].get_feature_names_out()
    imp = pd.Series(reg.named_steps["model"].feature_importances_, index=names).sort_values(ascending=False)
    syn = students.set_index("id")["is_synthetic"]
    metrics = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "data": {"rows": int(len(data)), "students": int(groups.nunique()), "train_rows": int(len(tr)), "test_rows": int(len(te)),
                 "test_students": int(groups.iloc[te].nunique()),
                 "synthetic_student_share": float(syn.reindex(groups.unique()).mean()),
                 "target": "mean score of the later ~30% of quizzes per student-subject; features use only earlier quizzes/activities"},
        "regression": {"model": "RandomForestRegressor", "mae": float(mean_absolute_error(y.iloc[te], pred)),
                       "rmse": float(np.sqrt(np.mean((y.iloc[te] - pred) ** 2))), "r2": float(r2_score(y.iloc[te], pred)),
                       "baseline_mae_early_avg": float(mean_absolute_error(y.iloc[te], X.iloc[te]["early_avg"])),
                       "cv_mae_mean": float(-cv.mean()), "cv_mae_std": float(cv.std())},
        "classification": {"model": "RandomForestClassifier", "accuracy": float(accuracy_score(y_cls.iloc[te], cls_pred)),
                           "f1_macro": float(f1_score(y_cls.iloc[te], cls_pred, average="macro", zero_division=0)),
                           "baseline_majority_accuracy": float((y_cls.iloc[te] == majority).mean()),
                           "labels": settings.CATEGORIES, "confusion_matrix": cm.tolist(),
                           "report": classification_report(y_cls.iloc[te], cls_pred, labels=settings.CATEGORIES,
                                                           output_dict=True, zero_division=0)},
        "feature_importance": {k: float(v) for k, v in imp.head(15).items()},
    }
    # deployment models: refit on all rows (the metrics above come from the held-out split)
    reg.fit(X, y)
    clf.fit(X, y_cls)

    sf = build_student_features(quizzes, acts)
    best = None
    sil = {}
    for k in (3, 4, 5):
        pipe = Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()),
                         ("km", KMeans(n_clusters=k, n_init=10, random_state=settings.RANDOM_STATE))])
        pipe.fit(sf[SEG_FEATURES])
        score = float(silhouette_score(pipe[:-1].transform(sf[SEG_FEATURES]), pipe.named_steps["km"].labels_))
        sil[k] = score
        if best is None or score > best[0]:
            best = (score, k, pipe)
    _, k, seg = best
    names_map = segment_names(seg.named_steps["km"].cluster_centers_)
    labels = seg.named_steps["km"].labels_
    metrics["segmentation"] = {"algorithm": "K-Means", "k": k, "silhouette_by_k": sil, "silhouette": sil[k], "students": int(len(sf)),
                               "cluster_names": {int(a): b for a, b in names_map.items()},
                               "cluster_sizes": {names_map[int(c)]: int((labels == c).sum()) for c in np.unique(labels)}}
    out = settings.model_dir()
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg, out / FILES["reg"])
    joblib.dump(clf, out / FILES["clf"])
    joblib.dump({"pipeline": seg, "names": names_map}, out / FILES["seg"])
    (out / FILES["metrics"]).write_text(json.dumps(metrics, indent=2))
    return metrics


def load_metrics() -> dict | None:
    p = settings.model_dir() / FILES["metrics"]
    return json.loads(p.read_text()) if p.exists() else None


if __name__ == "__main__":
    m = train_all()
    print(json.dumps({k: m[k] for k in ("data", "regression")}, indent=2))
    print("classification:", {k: round(v, 3) for k, v in m["classification"].items() if isinstance(v, float)})
    print("segmentation:", m["segmentation"]["k"], m["segmentation"]["cluster_sizes"])
