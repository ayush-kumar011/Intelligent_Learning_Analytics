"""Synthetic cohort generator (clearly flagged is_synthetic=1) + DB seeding.

Usage:  python -m data.generate_dataset --students 300 [--export-csv]
No real student data is used. The generating process (latent ability/motivation -> study effort ->
scores with learning curve, topic weaknesses and noise) is documented in README.md.
"""
import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import settings
from config.curriculum import ACTIVITY_TYPES, CURRICULUM
from database import db, seed
from services import auth

FIRST = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya", "Meera", "Rohan", "Saanvi", "Arjun", "Neha",
         "Priya", "Rahul", "Sneha", "Karan", "Pooja", "Vikram", "Riya", "Siddharth", "Tanvi", "Yash", "Zoya", "Aman"]
LAST = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Reddy", "Nair", "Mishra", "Khan", "Joshi", "Iyer", "Das", "Mehta", "Rao"]


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def generate(n_students: int, seed_value: int = settings.RANDOM_STATE, term_days: int = 98, end_date: date | None = None):
    rng = np.random.default_rng(seed_value)
    end = end_date or date.today()
    start = end - timedelta(days=term_days)
    students, quizzes, activities = [], [], []
    for i in range(n_students):
        ability = rng.normal()
        motivation = 0.4 * ability + np.sqrt(1 - 0.16) * rng.normal()
        hours = float(np.clip(8 + 3.5 * motivation + rng.normal(0, 1.5), 1, 30))
        attendance = float(np.clip(80 + 7 * motivation + 3 * ability + rng.normal(0, 5), 40, 100))
        sleep = float(np.clip(rng.normal(7, 1.1), 4, 10))
        gpa = float(np.clip(2.8 + 0.5 * ability + 0.2 * motivation + rng.normal(0, 0.25), 1.0, 4.0))
        students.append({"idx": i, "full_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "age": int(rng.integers(17, 25)),
                         "grade_level": str(rng.choice(settings.GRADE_LEVELS[:4])),
                         "study_hours_per_week": round(hours, 1), "attendance_pct": round(attendance, 1),
                         "sleep_hours": round(sleep, 1), "prior_gpa": round(gpa, 2)})
        for subject, topics in CURRICULUM.items():
            aptitude = ability + rng.normal(0, 0.6)
            effort = hours * rng.uniform(0.7, 1.3) / len(CURRICULUM)  # weekly hours on this subject
            weak = set(rng.choice(len(topics), size=int(rng.integers(1, 3)), replace=False).tolist())
            n_q = int(np.clip(round(9 + 2.5 * motivation + rng.normal(0, 1.5)), 3, 18))
            t_frac = np.sort(rng.uniform(0.02, 1.0, n_q))
            noise_sd = 6 + 3 * (1 - _sigmoid(motivation))
            for t in t_frac:
                ti = int(rng.integers(0, len(topics)))
                topic, diff = topics[ti]
                score = (64 + 10 * aptitude + 3.0 * (effort - 1.3)
                         + 8 * t * np.clip(effort / 1.3, 0.3, 2.5) * 0.6
                         - 3.5 * (diff - 2) - (12 if ti in weak else 0) + 0.15 * (attendance - 80)
                         + rng.normal(0, noise_sd))
                quizzes.append({"student_idx": i, "subject": subject, "topic": topic,
                                "score": round(float(np.clip(score, 5, 100)), 1),
                                "quiz_date": (start + timedelta(days=int(t * term_days))).isoformat(),
                                "time_taken_min": round(float(np.clip(rng.normal(12 + 2 * diff, 3), 4, 40)), 1)})
            n_a = int(max(2, round(n_q * rng.uniform(1.2, 2.2) * (0.6 + 0.4 * np.clip(effort / 1.3, 0.2, 2)))))
            p_done = float(np.clip(0.6 + 0.12 * motivation, 0.2, 0.97))
            for _ in range(n_a):
                activities.append({"student_idx": i, "subject": subject, "topic": topics[int(rng.integers(0, len(topics)))][0],
                                   "activity_type": str(rng.choice(ACTIVITY_TYPES, p=[.3, .2, .25, .1, .15])),
                                   "duration_min": round(float(np.clip(rng.lognormal(np.log(25 + 6 * effort), 0.4), 5, 150)), 1),
                                   "completed": int(rng.random() < p_done),
                                   "activity_date": (start + timedelta(days=int(rng.integers(0, term_days + 1)))).isoformat()})
    s, q, a = pd.DataFrame(students), pd.DataFrame(quizzes), pd.DataFrame(activities)
    # inject realistic missingness into profile fields (handled by median imputation in the ML pipeline)
    for col, p in [("sleep_hours", 0.05), ("attendance_pct", 0.04), ("prior_gpa", 0.03)]:
        s.loc[rng.random(len(s)) < p, col] = np.nan
    return s, q, a


def seed_database(n_students: int | None = None, seed_value: int = settings.RANDOM_STATE) -> int:
    n_students = n_students or settings.n_synthetic_students()
    db.init_db()
    seed.seed_reference_data()
    s, q, a = generate(n_students, seed_value)
    subj = {r.name: r.id for r in db.read_df("SELECT id, name FROM subjects").itertuples()}
    topics = {(r.subject, r.topic): r.topic_id for r in db.read_df(
        "SELECT t.id AS topic_id, s.name AS subject, t.name AS topic FROM topics t JOIN subjects s ON s.id=t.subject_id").itertuples()}
    none = lambda x: None if pd.isna(x) else float(x)
    with db.get_conn() as c:
        ids = {}
        for r in s.itertuples():
            ids[r.idx] = c.execute(
                "INSERT INTO students(full_name,age,grade_level,study_hours_per_week,attendance_pct,sleep_hours,prior_gpa,is_synthetic) "
                "VALUES (?,?,?,?,?,?,?,1)",
                (r.full_name, r.age, r.grade_level, r.study_hours_per_week, none(r.attendance_pct), none(r.sleep_hours),
                 none(r.prior_gpa))).lastrowid
        c.executemany(
            "INSERT INTO quiz_results(student_id,subject_id,topic_id,score,max_score,quiz_date,time_taken_min) VALUES (?,?,?,?,100,?,?)",
            [(ids[r.student_idx], subj[r.subject], topics[(r.subject, r.topic)], r.score, r.quiz_date, r.time_taken_min)
             for r in q.itertuples()])
        c.executemany(
            "INSERT INTO learning_activities(student_id,subject_id,topic_id,activity_type,duration_min,completed,activity_date) VALUES (?,?,?,?,?,?,?)",
            [(ids[r.student_idx], subj[r.subject], topics[(r.subject, r.topic)], r.activity_type, r.duration_min, r.completed, r.activity_date)
             for r in a.itertuples()])
        # one loginable demo account bound to the first synthetic student
        uid = c.execute("INSERT INTO users(username,email,password_hash,role) VALUES (?,?,?,'student')",
                        (settings.DEMO_STUDENT_USERNAME, "demo@example.local",
                         auth.hash_password(settings.DEMO_STUDENT_PASSWORD))).lastrowid
        c.execute("UPDATE students SET user_id=?, full_name='Demo Student' WHERE id=?", (uid, ids[0]))
    return n_students


def export_csv(out_dir: Path | None = None, n_students: int | None = None) -> Path:
    out_dir = out_dir or Path(__file__).parent / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)
    s, q, a = generate(n_students or settings.n_synthetic_students())
    s.to_csv(out_dir / "students.csv", index=False)
    q.to_csv(out_dir / "quiz_results.csv", index=False)
    a.to_csv(out_dir / "learning_activities.csv", index=False)
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=None)
    ap.add_argument("--export-csv", action="store_true")
    args = ap.parse_args()
    db.init_db()
    if db.scalar("SELECT COUNT(*) FROM students WHERE is_synthetic=1"):
        raise SystemExit("Synthetic data already present. Delete the database file to regenerate.")
    print(f"Seeded {seed_database(args.students)} synthetic students into {settings.db_path()}")
    if args.export_csv:
        print("CSV exported to", export_csv(n_students=args.students))
