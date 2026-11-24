"""Feature engineering. Leakage rule: in "train" mode the target (mean of the LATER quizzes) is computed
from quizzes/activities strictly after the cutoff, and NOTHING after the cutoff reaches the features."""
import numpy as np
import pandas as pd

NUM_FEATURES = ["early_avg", "early_std", "early_last3", "early_trend", "n_quizzes", "avg_time_per_quiz",
                "activity_min_per_week", "activity_count", "completion_rate", "active_days",
                "study_hours_per_week", "attendance_pct", "sleep_hours", "prior_gpa"]
CAT_FEATURES = ["subject"]
SEG_FEATURES = ["avg_score", "score_std", "score_trend", "minutes_per_week", "active_days_ratio",
                "completion_rate", "quizzes_per_week"]
PROFILE_COLS = ["study_hours_per_week", "attendance_pct", "sleep_hours", "prior_gpa"]


def _slope(y) -> float:
    return float(np.polyfit(np.arange(len(y)), y, 1)[0]) if len(y) >= 2 else 0.0


def build_subject_features(quizzes, activities, students, mode="inference", early_frac=0.7, min_quizzes=3):
    """One row per (student, subject). mode='train' adds `target_score` (mean of later quizzes)."""
    rows = []
    q_all = quizzes.copy()
    q_all["quiz_date"] = pd.to_datetime(q_all["quiz_date"])
    acts = activities.copy()
    acts["activity_date"] = pd.to_datetime(acts["activity_date"])
    act_groups = {k: g for k, g in acts.groupby(["student_id", "subject"])}
    prof = students.set_index("id")
    for (sid, subj), q in q_all.groupby(["student_id", "subject"]):
        q = q.sort_values(["quiz_date", "id"])
        n = len(q)
        if mode == "train":
            if n < 5:
                continue
            k = min(max(3, int(np.ceil(early_frac * n))), n - 1)
            early, late = q.iloc[:k], q.iloc[k:]
            target, cutoff = float(late["score_pct"].mean()), early["quiz_date"].max()
        else:
            if n < min_quizzes:
                continue
            early, target, cutoff = q, np.nan, None
        a = act_groups.get((sid, subj))
        if a is not None and cutoff is not None:
            a = a[a["activity_date"] <= cutoff]
        s = early["score_pct"].to_numpy(float)
        end = early["quiz_date"].max()
        first = early["quiz_date"].min()
        if a is not None and len(a):
            first, end = min(first, a["activity_date"].min()), max(end, a["activity_date"].max())
        weeks = max((end - first).days / 7, 1.0)
        has_a = a is not None and len(a) > 0
        row = {"student_id": sid, "subject": subj, "early_avg": s.mean(), "early_std": s.std(ddof=0),
               "early_last3": s[-3:].mean(), "early_trend": _slope(s), "n_quizzes": len(s),
               "avg_time_per_quiz": early["time_taken_min"].mean(),
               "activity_min_per_week": (a["duration_min"].sum() / weeks) if has_a else 0.0,
               "activity_count": len(a) if has_a else 0,
               "completion_rate": a["completed"].mean() if has_a else np.nan,
               "active_days": a["activity_date"].nunique() if has_a else 0}
        for c in PROFILE_COLS:
            row[c] = prof.at[sid, c] if sid in prof.index else np.nan
        if mode == "train":
            row["target_score"] = target
        rows.append(row)
    cols = ["student_id", "subject"] + NUM_FEATURES + (["target_score"] if mode == "train" else [])
    return pd.DataFrame(rows, columns=cols)


def build_student_features(quizzes, activities, min_quizzes=5):
    """One row per student for K-Means segmentation (uses all data; unsupervised, no target involved)."""
    acts = activities.copy()
    acts["activity_date"] = pd.to_datetime(acts["activity_date"])
    rows = []
    ag = {k: g for k, g in acts.groupby("student_id")}
    for sid, q in quizzes.groupby("student_id"):
        if len(q) < min_quizzes:
            continue
        q = q.sort_values(["quiz_date", "id"])
        s = q["score_pct"].to_numpy(float)
        a = ag.get(sid)
        dates = set(pd.to_datetime(q["quiz_date"]).dt.date)
        first, end = q["quiz_date"].min(), q["quiz_date"].max()
        if a is not None and len(a):
            dates |= set(a["activity_date"].dt.date)
            first, end = min(first, a["activity_date"].min()), max(end, a["activity_date"].max())
        span_days = max((end - first).days, 1)
        weeks = max(span_days / 7, 1.0)
        rows.append({"student_id": sid, "avg_score": s.mean(), "score_std": s.std(ddof=0), "score_trend": _slope(s),
                     "minutes_per_week": (a["duration_min"].sum() / weeks) if a is not None and len(a) else 0.0,
                     "active_days_ratio": min(len(dates) / (span_days + 1), 1.0),
                     "completion_rate": a["completed"].mean() if a is not None and len(a) else np.nan,
                     "quizzes_per_week": len(s) / weeks})
    return pd.DataFrame(rows, columns=["student_id"] + SEG_FEATURES)
