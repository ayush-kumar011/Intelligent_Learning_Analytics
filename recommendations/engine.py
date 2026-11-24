"""Rule + model based recommendation engine. Every recommendation is computed from the student's records
(topic mastery, recency, trend, engagement) and from model outputs (predicted score/category, segment, risk).
Only the sentence templates are static; selection, ordering, numbers, difficulty and dates are data-driven."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from analytics import metrics
from config import settings
from database import repository as repo

TARGET = settings.MASTERY_TARGET


def _level_for(mastery: float) -> str:
    return "Beginner" if mastery < 50 else "Intermediate" if mastery < 70 else "Advanced"


def _interval_days(mastery: float) -> int:
    return 1 if mastery < 50 else 3 if mastery < 65 else 7 if mastery < 80 else 14


def generate(student_id: int, persist: bool = True, today: date | None = None) -> list[dict]:
    today = today or date.today()
    student = repo.get_student(student_id)
    if student is None:
        raise ValueError(f"Unknown student {student_id}")
    mastery = metrics.topic_mastery(student_id, today)
    att = mastery[mastery.attempts > 0].copy()
    recs: list[dict] = []

    def add(**kw):
        kw.setdefault("priority", 2)
        recs.append(kw)

    # ---- cold start: no data yet ----
    if att.empty:
        subs = repo.get_subjects()
        add(rec_type="engagement", priority=1, title="Take a diagnostic quiz in each subject",
            detail=f"No quiz results are recorded yet, so personalised recommendations are not possible. Log at least 3 quizzes in each of "
                   f"your {len(subs)} subjects on the 'Log Learning' page; predictions need >= 3 quizzes per subject.")
        add(rec_type="engagement", priority=2, title="Log your first learning activities",
            detail="Recording study sessions (video, reading, practice) lets the system measure your weekly study time and consistency.")
        return _finish(student_id, recs, persist, today)

    # ---- learning gaps (topic level) ----
    gaps = att[(att.mastery < TARGET) | (att.gap_vs_peers > 10)].copy()
    gaps["severity"] = (TARGET - gaps.mastery).clip(lower=0) + gaps.gap_vs_peers.fillna(0).clip(lower=0) * 0.5
    gaps = gaps.sort_values("severity", ascending=False).head(4)
    for r in gaps.itertuples():
        peer = "" if pd.isna(r.peer_avg) else f" and {r.gap_vs_peers:+.0f} points vs. the cohort average ({r.peer_avg:.0f}%)"
        add(rec_type="learning_gap", subject_id=int(r.subject_id), topic_id=int(r.topic_id),
            priority=1 if r.mastery < 50 else 2,
            title=f"Learning gap: {r.topic} ({r.subject})",
            detail=f"Recency-weighted mastery is {r.mastery:.0f}% over {r.attempts} attempt(s): {max(TARGET - r.mastery, 0):.0f} points "
                   f"below the {TARGET:.0f}% target{peer}.")
        mats = repo.get_materials(int(r.topic_id))
        if len(mats):
            lvl = _level_for(r.mastery)
            order = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
            mats = mats.assign(d=(mats.level.map(order) - order[lvl]).abs()).sort_values(["d", "est_minutes"]).head(1)
            for m in mats.itertuples():
                link = f" - {m.url}" if m.url else ""
                add(rec_type="material", subject_id=int(r.subject_id), topic_id=int(r.topic_id), priority=2,
                    title=f"Study material: {m.title}",
                    detail=f"{m.level} {m.material_type}, about {m.est_minutes} min. Chosen for your {r.mastery:.0f}% mastery on {r.topic}{link}")
        else:
            add(rec_type="material", subject_id=int(r.subject_id), topic_id=int(r.topic_id), priority=3,
                title=f"No catalogue material yet for {r.topic}",
                detail="Ask your teacher/admin to add a resource for this topic.")

    # ---- practice quizzes ----
    cand = mastery[(mastery.attempts == 0) | ((mastery.attempts < 3) & (mastery.mastery < 80)) |
                   (mastery.trend < -2) | ((mastery.mastery >= TARGET) & (mastery.mastery < 80))].copy()
    studied_subjects = set(att.subject_id)
    cand = cand[cand.subject_id.isin(studied_subjects)]  # only subjects the student has started
    cand["rank"] = np.where(cand.attempts == 0, 2, 0) + np.where(cand.trend < -2, -1, 0) + cand.mastery.fillna(60) / 100
    for r in cand.sort_values("rank").head(3).itertuples():
        if r.attempts == 0:
            title, why, diff, n = f"Diagnostic quiz: {r.topic} ({r.subject})", "You have not attempted this topic yet.", "Easy", 5
        else:
            diff = "Easy" if r.mastery < 50 else "Medium" if r.mastery < 75 else "Hard"
            n = 5 if r.mastery < 50 else 8 if r.mastery < 75 else 10
            why = (f"Mastery {r.mastery:.0f}% with {r.attempts} attempt(s)" +
                   (f"; scores are trending down ({r.trend:+.1f} per quiz)." if r.trend < -2 else "."))
            title = f"Practice quiz: {r.topic} ({r.subject})"
        add(rec_type="practice_quiz", subject_id=int(r.subject_id), topic_id=int(r.topic_id), priority=2 if r.attempts else 3,
            title=title, detail=f"{why} Suggested: {n} questions, {diff} difficulty.")

    # ---- revision schedule (spaced repetition) ----
    weekly_budget = float(student.get("study_hours_per_week") or 8) * 60
    sched = att[att.mastery < 85].copy()
    sched["due"] = [max(l.date() + timedelta(days=_interval_days(m)), today) for l, m in zip(sched.last_date, sched.mastery)]
    sched = sched.sort_values(["due", "mastery"]).head(5)
    if len(sched):
        mins = int(np.clip(round(weekly_budget * 0.6 / len(sched) / 5) * 5, 15, 60))
        for r in sched.itertuples():
            overdue = (today - (r.last_date.date() + timedelta(days=_interval_days(r.mastery)))).days
            add(rec_type="revision", subject_id=int(r.subject_id), topic_id=int(r.topic_id),
                priority=1 if r.due <= today and r.mastery < 60 else 2, due_date=r.due.isoformat(),
                title=f"Revise {r.topic} on {r.due.strftime('%a %d %b')}",
                detail=f"{mins} min session. Mastery {r.mastery:.0f}% -> review every {_interval_days(r.mastery)} day(s)"
                       + (f"; overdue by {overdue} day(s)." if overdue > 0 else "."))

    # ---- progress-adaptive + model-driven (subject level) ----
    q = repo.get_quizzes(student_id)
    perf = repo.get_performance(student_id).set_index("subject_id")
    for sid, g in q.groupby("subject_id"):
        g = g.sort_values(["quiz_date", "id"])
        name = g.subject.iloc[0]
        if len(g) >= 6:
            recent, before = g.score_pct.iloc[-3:].mean(), g.score_pct.iloc[:-3].mean()
            d = recent - before
            if d >= 5:
                add(rec_type="progress", subject_id=int(sid), priority=3, title=f"{name}: you are improving - raise the difficulty",
                    detail=f"Your last 3 quizzes average {recent:.0f}% vs {before:.0f}% before (+{d:.0f}). Move to Intermediate/Advanced material.")
            elif d <= -5:
                add(rec_type="progress", subject_id=int(sid), priority=1, title=f"{name}: scores are dropping - revisit fundamentals",
                    detail=f"Your last 3 quizzes average {recent:.0f}% vs {before:.0f}% before ({d:.0f}). Re-attempt recent quizzes and review the errors before new content.")
        if sid in perf.index and pd.notna(perf.at[sid, "predicted_score"]):
            ps, cat = float(perf.at[sid, "predicted_score"]), perf.at[sid, "predicted_category"]
            if cat in ("At Risk", "Average") and ps < TARGET:
                add(rec_type="subject_alert", subject_id=int(sid), priority=1 if cat == "At Risk" else 2,
                    title=f"{name}: projected {ps:.0f}% ({cat})",
                    detail=f"The model projects your upcoming {name} quiz average at {ps:.0f}% (category: {cat}). Prioritise this subject in your weekly plan.")
    ins = repo.get_insights(student_id)
    a = repo.get_activities(student_id)
    if len(a):
        weeks = max((a.activity_date.max() - a.activity_date.min()).days / 7, 1.0)
        mpw = a.duration_min.sum() / weeks
        cohort = metrics.db.scalar("SELECT SUM(duration_min)/COUNT(DISTINCT student_id)/14.0 FROM learning_activities") or mpw
        if mpw < 0.7 * cohort:
            add(rec_type="engagement", priority=2, title="Increase your weekly study time",
                detail=f"You log about {mpw:.0f} min/week vs a cohort average of {cohort:.0f}. Aim for {min(mpw * 1.25 + 30, cohort):.0f} min/week in short, regular sessions.")
        if ins and ins.get("segment") and "Disengaged" in ins["segment"]:
            add(rec_type="engagement", priority=1, title="Build a consistent routine",
                detail=f"You are grouped in the '{ins['segment']}' segment (low activity and scores). Try 3 fixed 25-minute sessions per week and log them.")
    if ins and ins.get("risk_level") == "High":
        add(rec_type="engagement", priority=1, title="High academic risk flagged",
            detail="Your overall projection is low. Consider meeting your teacher this week to agree on a recovery plan.")
    return _finish(student_id, recs, persist, today)


def _finish(student_id, recs, persist, today):
    skip = repo.recently_done(student_id)
    recs = [r for r in recs if (r["rec_type"], r.get("topic_id")) not in skip]
    recs.sort(key=lambda r: (r.get("priority", 2), r.get("due_date") or "9999"))
    if persist:
        repo.replace_recommendations(student_id, recs)
    return recs
