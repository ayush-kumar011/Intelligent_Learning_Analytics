"""Loads trained artifacts and writes predictions/segments/risk into the database."""
import joblib
import numpy as np
import pandas as pd

from config import settings
from database import repository as repo
from models.features import CAT_FEATURES, NUM_FEATURES, SEG_FEATURES, build_student_features, build_subject_features
from models.trainer import FILES

_cache: dict = {}


def _load(key: str):
    path = settings.model_dir() / FILES[key]
    mtime = path.stat().st_mtime
    hit = _cache.get(str(path))
    if hit and hit[0] == mtime:
        return hit[1]
    obj = joblib.load(path)
    _cache[str(path)] = (mtime, obj)
    return obj


def models_available() -> bool:
    return all((settings.model_dir() / FILES[k]).exists() for k in ("reg", "clf", "seg"))


def predict_subjects(feat: pd.DataFrame) -> pd.DataFrame:
    if feat.empty:
        return feat.assign(predicted_score=[], predicted_category=[], category_confidence=[])
    X = feat[NUM_FEATURES + CAT_FEATURES]
    clf = _load("clf")
    proba = clf.predict_proba(X)
    out = feat[["student_id", "subject"]].copy()
    out["predicted_score"] = np.clip(_load("reg").predict(X), 0, 100)
    out["predicted_category"] = clf.predict(X)
    out["category_confidence"] = proba.max(axis=1)
    return out


def assign_segments(sf: pd.DataFrame) -> pd.DataFrame:
    if sf.empty:
        return sf.assign(segment=[])
    art = _load("seg")
    labels = art["pipeline"].predict(sf[SEG_FEATURES])
    return sf[["student_id"]].assign(segment=[art["names"][int(l)] for l in labels])


def _risk(basis: float, any_at_risk: bool, trend: float) -> str:
    if basis < 55 or (basis < 65 and trend < -1):
        return "High"
    if basis < 70 or any_at_risk:
        return "Medium"
    return "Low"


def refresh(student_ids=None) -> int:
    """Recompute student_performance + student_insights (all students, or the given ids). Returns #students updated."""
    if not models_available():
        raise RuntimeError("Models not trained yet. Run `python -m models.trainer` or use the Model Lab page.")
    quizzes, acts = repo.get_quizzes(), repo.get_activities()
    students = repo.list_students().rename(columns={"student_id": "id"})
    if student_ids is not None:
        ids = set(student_ids)
        quizzes, acts, students = quizzes[quizzes.student_id.isin(ids)], acts[acts.student_id.isin(ids)], students[students.id.isin(ids)]
    if quizzes.empty:
        return 0
    subj_ids = repo.get_subjects().set_index("subject")["subject_id"].to_dict()
    pred = predict_subjects(build_subject_features(quizzes, acts, students, mode="inference")).set_index(["student_id", "subject"])
    seg = assign_segments(build_student_features(quizzes, acts)).set_index("student_id")["segment"].to_dict()
    perf_rows, insight_rows = [], []
    a_by = {k: g for k, g in acts.groupby(["student_id", "subject"])}
    for (sid, subj), q in quizzes.groupby(["student_id", "subject"]):
        a = a_by.get((sid, subj))
        p = pred.loc[(sid, subj)] if (sid, subj) in pred.index else None
        perf_rows.append((int(sid), int(subj_ids[subj]), float(q.score_pct.mean()), int(len(q)),
                          float(a.duration_min.sum()) if a is not None else 0.0,
                          float(a.completed.mean()) if a is not None else None,
                          None if p is None else float(p.predicted_score), None if p is None else str(p.predicted_category)))
    repo.save_performance(perf_rows)
    for sid, q in quizzes.groupby("student_id"):
        sp = pred.loc[sid] if sid in pred.index.get_level_values(0) else pd.DataFrame()
        overall = float(sp.predicted_score.mean()) if len(sp) else None
        scores = q.sort_values(["quiz_date", "id"]).score_pct.to_numpy(float)
        trend = float(np.polyfit(np.arange(len(scores)), scores, 1)[0]) if len(scores) >= 3 else 0.0
        basis = overall if overall is not None else float(scores.mean())
        any_risk = bool(len(sp) and (sp.predicted_category == "At Risk").any())
        insight_rows.append((int(sid), seg.get(sid, "Insufficient data"), _risk(basis, any_risk, trend), overall))
    repo.save_insights(insight_rows)
    return len(insight_rows)
