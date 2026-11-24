import sqlite3

import pytest

from database import db

TABLES = {"users", "students", "subjects", "topics", "materials", "learning_activities", "quiz_results",
          "student_performance", "student_insights", "recommendations"}


def test_connectivity_and_tables():
    assert db.scalar("SELECT 1") == 1
    names = {r["name"] for r in db.read_df("SELECT name FROM sqlite_master WHERE type='table'").to_dict("records")}
    assert TABLES <= names


def test_foreign_keys_and_checks_enforced():
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO quiz_results(student_id,subject_id,topic_id,score,max_score,quiz_date) VALUES (999999,1,1,50,100,'2025-01-01')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO quiz_results(student_id,subject_id,topic_id,score,max_score,quiz_date) VALUES (1,1,1,150,100,'2025-01-01')")


def test_data_persists_across_connections():
    n1 = db.scalar("SELECT COUNT(*) FROM quiz_results")
    assert n1 > 1000 and db.scalar("SELECT COUNT(*) FROM quiz_results") == n1
