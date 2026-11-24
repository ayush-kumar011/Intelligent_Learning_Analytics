"""All SQL lives here. Other layers call these functions instead of writing queries."""
from datetime import datetime

import pandas as pd

from database import db

_STUDENT_EDITABLE = {"full_name", "age", "grade_level", "study_hours_per_week", "attendance_pct",
                     "sleep_hours", "prior_gpa", "learning_goal"}


# ---------- users / students ----------
def get_user(username: str):
    with db.get_conn() as c:
        r = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(r) if r else None


def get_student(student_id: int):
    with db.get_conn() as c:
        r = c.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        return dict(r) if r else None


def get_student_by_user(user_id: int):
    with db.get_conn() as c:
        r = c.execute("SELECT * FROM students WHERE user_id = ?", (user_id,)).fetchone()
        return dict(r) if r else None


def update_student(student_id: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in _STUDENT_EDITABLE}
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE students SET {cols} WHERE id = ?", (*fields.values(), student_id))


def update_password(user_id: int, password_hash: str) -> None:
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def list_students() -> pd.DataFrame:
    return db.read_df(
        """SELECT s.id AS student_id, s.full_name, s.age, s.grade_level, s.study_hours_per_week,
                  s.attendance_pct, s.sleep_hours, s.prior_gpa, s.is_synthetic, s.created_at,
                  u.username, u.email, i.segment, i.risk_level, i.overall_predicted
           FROM students s LEFT JOIN users u ON u.id = s.user_id
           LEFT JOIN student_insights i ON i.student_id = s.id
           ORDER BY s.id""")


# ---------- reference data ----------
def get_subjects() -> pd.DataFrame:
    return db.read_df("SELECT id AS subject_id, name AS subject FROM subjects ORDER BY name")


def get_topics(subject_id: int | None = None) -> pd.DataFrame:
    sql = """SELECT t.id AS topic_id, t.subject_id, s.name AS subject, t.name AS topic, t.difficulty
             FROM topics t JOIN subjects s ON s.id = t.subject_id"""
    if subject_id is not None:
        return db.read_df(sql + " WHERE t.subject_id = ? ORDER BY t.id", (subject_id,))
    return db.read_df(sql + " ORDER BY s.name, t.id")


def get_materials(topic_id: int | None = None) -> pd.DataFrame:
    sql = """SELECT m.id AS material_id, m.topic_id, t.name AS topic, s.name AS subject, m.title,
                    m.material_type, m.level, m.url, m.est_minutes, m.description
             FROM materials m JOIN topics t ON t.id = m.topic_id JOIN subjects s ON s.id = t.subject_id"""
    if topic_id is not None:
        return db.read_df(sql + " WHERE m.topic_id = ?", (topic_id,))
    return db.read_df(sql + " ORDER BY s.name, t.name, m.level")


def add_material(topic_id, title, material_type, level, url, est_minutes, description) -> int:
    return db.execute(
        "INSERT INTO materials(topic_id,title,material_type,level,url,est_minutes,description) VALUES (?,?,?,?,?,?,?)",
        (topic_id, title, material_type, level, url or None, est_minutes, description or None))


# ---------- learning data ----------
def add_quiz(student_id, subject_id, topic_id, score, max_score, quiz_date, time_taken_min) -> int:
    return db.execute(
        "INSERT INTO quiz_results(student_id,subject_id,topic_id,score,max_score,quiz_date,time_taken_min) "
        "VALUES (?,?,?,?,?,?,?)",
        (int(student_id), int(subject_id), int(topic_id), float(score), float(max_score), str(quiz_date),
         None if time_taken_min is None else float(time_taken_min)))


def add_activity(student_id, subject_id, topic_id, activity_type, duration_min, completed, activity_date) -> int:
    return db.execute(
        "INSERT INTO learning_activities(student_id,subject_id,topic_id,activity_type,duration_min,completed,activity_date) "
        "VALUES (?,?,?,?,?,?,?)",
        (int(student_id), int(subject_id), None if topic_id is None else int(topic_id), activity_type, float(duration_min),
         int(completed), str(activity_date)))


def get_quizzes(student_id: int | None = None) -> pd.DataFrame:
    sql = """SELECT q.id, q.student_id, q.subject_id, s.name AS subject, q.topic_id, t.name AS topic,
                    q.score * 100.0 / q.max_score AS score_pct, q.quiz_date, q.time_taken_min
             FROM quiz_results q JOIN subjects s ON s.id = q.subject_id JOIN topics t ON t.id = q.topic_id"""
    if student_id is not None:
        df = db.read_df(sql + " WHERE q.student_id = ? ORDER BY q.quiz_date, q.id", (student_id,))
    else:
        df = db.read_df(sql + " ORDER BY q.quiz_date, q.id")
    df["quiz_date"] = pd.to_datetime(df["quiz_date"])
    return df


def get_activities(student_id: int | None = None) -> pd.DataFrame:
    sql = """SELECT a.id, a.student_id, a.subject_id, s.name AS subject, a.topic_id, t.name AS topic,
                    a.activity_type, a.duration_min, a.completed, a.activity_date
             FROM learning_activities a JOIN subjects s ON s.id = a.subject_id
             LEFT JOIN topics t ON t.id = a.topic_id"""
    if student_id is not None:
        df = db.read_df(sql + " WHERE a.student_id = ? ORDER BY a.activity_date, a.id", (student_id,))
    else:
        df = db.read_df(sql + " ORDER BY a.activity_date, a.id")
    df["activity_date"] = pd.to_datetime(df["activity_date"])
    return df


def get_peer_topic_avg() -> pd.DataFrame:
    return db.read_df("SELECT topic_id, AVG(score*100.0/max_score) AS peer_avg FROM quiz_results GROUP BY topic_id")


def get_peer_subject_avg() -> pd.DataFrame:
    return db.read_df("SELECT subject_id, AVG(score*100.0/max_score) AS cohort_avg FROM quiz_results GROUP BY subject_id")


# ---------- model outputs ----------
def save_performance(rows: list[tuple]) -> None:
    """rows: (student_id, subject_id, avg_score, quizzes_taken, total_time_min, completion_rate, predicted_score, predicted_category)"""
    db.executemany(
        """INSERT INTO student_performance(student_id,subject_id,avg_score,quizzes_taken,total_time_min,
                  completion_rate,predicted_score,predicted_category,updated_at)
           VALUES (?,?,?,?,?,?,?,?,datetime('now'))
           ON CONFLICT(student_id,subject_id) DO UPDATE SET avg_score=excluded.avg_score,
                  quizzes_taken=excluded.quizzes_taken, total_time_min=excluded.total_time_min,
                  completion_rate=excluded.completion_rate, predicted_score=excluded.predicted_score,
                  predicted_category=excluded.predicted_category, updated_at=excluded.updated_at""", rows)


def save_insights(rows: list[tuple]) -> None:
    """rows: (student_id, segment, risk_level, overall_predicted)"""
    db.executemany(
        """INSERT INTO student_insights(student_id,segment,risk_level,overall_predicted,updated_at)
           VALUES (?,?,?,?,datetime('now'))
           ON CONFLICT(student_id) DO UPDATE SET segment=excluded.segment, risk_level=excluded.risk_level,
                  overall_predicted=excluded.overall_predicted, updated_at=excluded.updated_at""", rows)


def get_performance(student_id: int | None = None) -> pd.DataFrame:
    sql = """SELECT p.*, s.name AS subject FROM student_performance p JOIN subjects s ON s.id = p.subject_id"""
    if student_id is not None:
        return db.read_df(sql + " WHERE p.student_id = ?", (student_id,))
    return db.read_df(sql)


def get_insights(student_id: int):
    with db.get_conn() as c:
        r = c.execute("SELECT * FROM student_insights WHERE student_id = ?", (student_id,)).fetchone()
        return dict(r) if r else None


# ---------- recommendations ----------
def replace_recommendations(student_id: int, recs: list[dict]) -> None:
    with db.get_conn() as c:
        c.execute("DELETE FROM recommendations WHERE student_id = ? AND status = 'active'", (student_id,))
        c.executemany(
            "INSERT INTO recommendations(student_id,subject_id,topic_id,rec_type,title,detail,priority,due_date) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(student_id, r.get("subject_id"), r.get("topic_id"), r["rec_type"], r["title"], r["detail"],
              r.get("priority", 2), r.get("due_date")) for r in recs])


def get_recommendations(student_id: int, status: str | None = "active") -> pd.DataFrame:
    sql = """SELECT r.id AS rec_id, r.rec_type, r.title, r.detail, r.priority, r.due_date, r.status, r.created_at,
                    r.subject_id, r.topic_id, s.name AS subject, t.name AS topic
             FROM recommendations r LEFT JOIN subjects s ON s.id = r.subject_id LEFT JOIN topics t ON t.id = r.topic_id
             WHERE r.student_id = ?"""
    params = (student_id,)
    if status:
        sql += " AND r.status = ?"
        params += (status,)
    return db.read_df(sql + " ORDER BY r.priority, r.due_date, r.id", params)


def set_recommendation_status(rec_id: int, student_id: int, status: str) -> None:
    db.execute("UPDATE recommendations SET status = ?, updated_at = ? WHERE id = ? AND student_id = ?",
               (status, datetime.now().isoformat(timespec="seconds"), rec_id, student_id))


def recently_done(student_id: int, days: int = 3) -> set:
    df = db.read_df("SELECT rec_type, topic_id FROM recommendations WHERE student_id = ? AND status = 'done' "
                    "AND updated_at >= datetime('now', ?)", (student_id, f"-{days} days"))
    return {(r.rec_type, None if pd.isna(r.topic_id) else int(r.topic_id)) for r in df.itertuples()}
