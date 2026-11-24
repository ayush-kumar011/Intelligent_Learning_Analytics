"""Analytics derived from database records. Pure functions returning DataFrames / dicts."""
import numpy as np
import pandas as pd

from config import settings
from database import db, repository as repo


def student_overview(student_id: int) -> dict:
    q, a = repo.get_quizzes(student_id), repo.get_activities(student_id)
    ins = repo.get_insights(student_id) or {}
    days = set(q.quiz_date.dt.date) | set(a.activity_date.dt.date)
    return {
        "avg_score": float(q.score_pct.mean()) if len(q) else None,
        "quizzes": int(len(q)),
        "total_hours": float(a.duration_min.sum() / 60) if len(a) else 0.0,
        "completion_rate": float(a.completed.mean() * 100) if len(a) else None,
        "active_days": len(days),
        "segment": ins.get("segment"), "risk": ins.get("risk_level"), "predicted": ins.get("overall_predicted"),
    }


def subject_performance(student_id: int) -> pd.DataFrame:
    q, a = repo.get_quizzes(student_id), repo.get_activities(student_id)
    subs = repo.get_subjects()
    out = subs.merge(q.groupby("subject_id").agg(avg_score=("score_pct", "mean"), quizzes=("id", "count")).reset_index(), how="left", on="subject_id")
    out = out.merge(a.groupby("subject_id").agg(minutes=("duration_min", "sum")).reset_index(), how="left", on="subject_id")
    out = out.merge(repo.get_peer_subject_avg(), how="left", on="subject_id")
    perf = repo.get_performance(student_id)[["subject_id", "predicted_score", "predicted_category"]]
    out = out.merge(perf, how="left", on="subject_id")
    out["quizzes"] = out["quizzes"].fillna(0).astype(int)
    out["minutes"] = out["minutes"].fillna(0.0)
    return out


def score_timeline(student_id: int) -> pd.DataFrame:
    q = repo.get_quizzes(student_id)
    if q.empty:
        return pd.DataFrame(columns=["week", "subject", "score"])
    q["week"] = q.quiz_date.dt.to_period("W").dt.start_time
    return q.groupby(["week", "subject"], as_index=False).agg(score=("score_pct", "mean"))


def weekly_time(student_id: int) -> pd.DataFrame:
    a = repo.get_activities(student_id)
    if a.empty:
        return pd.DataFrame(columns=["week", "activity_type", "minutes"])
    a["week"] = a.activity_date.dt.to_period("W").dt.start_time
    return a.groupby(["week", "activity_type"], as_index=False).agg(minutes=("duration_min", "sum"))


def topic_mastery(student_id: int, today=None) -> pd.DataFrame:
    """Recency-weighted mastery per topic (half-life 30 days) for ALL topics; unattempted topics have attempts=0."""
    today = pd.Timestamp(today or pd.Timestamp.today().normalize())
    topics = repo.get_topics()
    q = repo.get_quizzes(student_id)
    if q.empty:
        agg = pd.DataFrame(columns=["topic_id", "mastery", "attempts", "last_date", "trend"])
    else:
        q = q.assign(w=0.5 ** ((today - q.quiz_date).dt.days.clip(lower=0) / 30.0))
        rows = []
        for tid, g in q.groupby("topic_id"):
            g = g.sort_values(["quiz_date", "id"])
            s = g.score_pct.to_numpy(float)
            rows.append({"topic_id": tid, "mastery": float((g.w * g.score_pct).sum() / g.w.sum()), "attempts": len(g),
                         "last_date": g.quiz_date.max(),
                         "trend": float(np.polyfit(np.arange(len(s)), s, 1)[0]) if len(s) >= 3 else np.nan})
        agg = pd.DataFrame(rows)
    out = topics.merge(agg, how="left", on="topic_id").merge(repo.get_peer_topic_avg(), how="left", on="topic_id")
    out["attempts"] = out["attempts"].fillna(0).astype(int)
    out["gap_vs_target"] = settings.MASTERY_TARGET - out["mastery"]
    out["gap_vs_peers"] = out["peer_avg"] - out["mastery"]
    return out


def assessment_history(student_id: int) -> pd.DataFrame:
    q = repo.get_quizzes(student_id)
    return q[["quiz_date", "subject", "topic", "score_pct", "time_taken_min"]].sort_values("quiz_date", ascending=False)


# ---------------- cohort / admin ----------------
def cohort_overview() -> dict:
    s = repo.list_students()
    return {
        "students": int(len(s)), "synthetic": int(s.is_synthetic.sum()), "real": int((s.is_synthetic == 0).sum()),
        "quizzes": int(db.scalar("SELECT COUNT(*) FROM quiz_results") or 0),
        "avg_score": db.scalar("SELECT AVG(score*100.0/max_score) FROM quiz_results"),
        "high_risk": int((s.risk_level == "High").sum()), "medium_risk": int((s.risk_level == "Medium").sum()),
    }


def students_table() -> pd.DataFrame:
    s = repo.list_students()
    q = db.read_df("SELECT student_id, AVG(score*100.0/max_score) AS avg_score, COUNT(*) AS quizzes FROM quiz_results GROUP BY student_id")
    a = db.read_df("SELECT student_id, SUM(duration_min)/60.0 AS hours FROM learning_activities GROUP BY student_id")
    out = s.merge(q, how="left", on="student_id").merge(a, how="left", on="student_id")
    out["source"] = np.where(out.is_synthetic == 1, "synthetic", "real")
    return out


def cohort_subject_stats() -> pd.DataFrame:
    return db.read_df("""SELECT s.name AS subject, AVG(q.score*100.0/q.max_score) AS avg_score, COUNT(*) AS quizzes,
                         COUNT(DISTINCT q.student_id) AS students FROM quiz_results q JOIN subjects s ON s.id=q.subject_id
                         GROUP BY s.name ORDER BY avg_score""")


def cohort_trend() -> pd.DataFrame:
    q = repo.get_quizzes()
    q["week"] = q.quiz_date.dt.to_period("W").dt.start_time
    return q.groupby("week", as_index=False).agg(avg_score=("score_pct", "mean"), quizzes=("id", "count"))


def score_distribution() -> pd.DataFrame:
    return db.read_df("SELECT student_id, AVG(score*100.0/max_score) AS avg_score FROM quiz_results GROUP BY student_id")


def weakest_topics_cohort(n: int = 8) -> pd.DataFrame:
    return db.read_df("""SELECT s.name AS subject, t.name AS topic, AVG(q.score*100.0/q.max_score) AS avg_score, COUNT(*) AS attempts
                         FROM quiz_results q JOIN topics t ON t.id=q.topic_id JOIN subjects s ON s.id=t.subject_id
                         GROUP BY t.id HAVING COUNT(*) >= 10 ORDER BY avg_score LIMIT ?""", (n,))
