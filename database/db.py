"""SQLite connection handling and schema."""
import sqlite3
from contextlib import contextmanager

import pandas as pd

from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student','admin')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    age INTEGER CHECK (age IS NULL OR age BETWEEN 10 AND 100),
    grade_level TEXT,
    study_hours_per_week REAL CHECK (study_hours_per_week IS NULL OR study_hours_per_week BETWEEN 0 AND 100),
    attendance_pct REAL CHECK (attendance_pct IS NULL OR attendance_pct BETWEEN 0 AND 100),
    sleep_hours REAL CHECK (sleep_hours IS NULL OR sleep_hours BETWEEN 0 AND 24),
    prior_gpa REAL CHECK (prior_gpa IS NULL OR prior_gpa BETWEEN 0 AND 4),
    learning_goal TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    difficulty INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 3),
    UNIQUE (subject_id, name)
);
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    material_type TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('Beginner','Intermediate','Advanced')),
    url TEXT,
    est_minutes INTEGER CHECK (est_minutes IS NULL OR est_minutes > 0),
    description TEXT
);
CREATE TABLE IF NOT EXISTS learning_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    topic_id INTEGER REFERENCES topics(id),
    activity_type TEXT NOT NULL,
    duration_min REAL NOT NULL CHECK (duration_min > 0),
    completed INTEGER NOT NULL DEFAULT 1 CHECK (completed IN (0,1)),
    activity_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    score REAL NOT NULL CHECK (score >= 0),
    max_score REAL NOT NULL DEFAULT 100 CHECK (max_score > 0),
    quiz_date TEXT NOT NULL,
    time_taken_min REAL CHECK (time_taken_min IS NULL OR time_taken_min > 0),
    CHECK (score <= max_score)
);
CREATE TABLE IF NOT EXISTS student_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    avg_score REAL,
    quizzes_taken INTEGER NOT NULL DEFAULT 0,
    total_time_min REAL NOT NULL DEFAULT 0,
    completion_rate REAL,
    predicted_score REAL,
    predicted_category TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, subject_id)
);
CREATE TABLE IF NOT EXISTS student_insights (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    segment TEXT,
    risk_level TEXT,
    overall_predicted REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subjects(id),
    topic_id INTEGER REFERENCES topics(id),
    rec_type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','done','dismissed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_quiz_student ON quiz_results(student_id, subject_id, quiz_date);
CREATE INDEX IF NOT EXISTS idx_act_student ON learning_activities(student_id, subject_id, activity_date);
CREATE INDEX IF NOT EXISTS idx_rec_student ON recommendations(student_id, status);
"""


def connect() -> sqlite3.Connection:
    path = settings.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def read_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute(sql: str, params: tuple = ()) -> int:
    with get_conn() as conn:
        return conn.execute(sql, params).lastrowid


def executemany(sql: str, rows) -> None:
    with get_conn() as conn:
        conn.executemany(sql, rows)


def scalar(sql: str, params: tuple = ()):
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return None if row is None else row[0]
