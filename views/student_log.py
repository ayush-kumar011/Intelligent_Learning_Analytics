from datetime import date

import streamlit as st

from config.curriculum import ACTIVITY_TYPES
from database import repository as repo
from models import predictor
from recommendations import engine
from utils.ui import require_role, table


def _refresh(student_id: int) -> None:
    if predictor.models_available():
        predictor.refresh([student_id])
    engine.generate(student_id)


def render():
    user = require_role("student")
    sid = user["student_id"]
    st.title("Log Learning")
    st.caption("Your entries feed your analytics, projections and recommendations.")
    subjects = repo.get_subjects()
    names = subjects.subject.tolist()
    t1, t2 = st.tabs(["Record a quiz", "Log a study activity"])
    with t1:
        subj = st.selectbox("Subject", names, key="q_subj")
        subject_id = int(subjects.loc[subjects.subject == subj, "subject_id"].iloc[0])
        topics = repo.get_topics(subject_id)
        with st.form("quiz_form", clear_on_submit=True):
            topic = st.selectbox("Topic", topics.topic.tolist())
            c = st.columns(3)
            score = c[0].number_input("Score", min_value=0.0, value=None, step=0.5, placeholder="e.g. 42")
            max_score = c[1].number_input("Out of", min_value=1.0, value=100.0, step=1.0)
            minutes = c[2].number_input("Time taken (min)", min_value=1.0, value=15.0, step=1.0)
            qdate = st.date_input("Date", value=date.today(), max_value=date.today())
            if st.form_submit_button("Save quiz result", type="primary"):
                if score is None:
                    st.error("Enter your score.")
                elif score > max_score:
                    st.error("Score cannot exceed the maximum score.")
                else:
                    tid = int(topics.loc[topics.topic == topic, "topic_id"].iloc[0])
                    repo.add_quiz(sid, subject_id, tid, score, max_score, qdate, minutes)
                    _refresh(sid)
                    st.success(f"Saved: {topic} - {score:g}/{max_score:g} ({score / max_score * 100:.0f}%). Analytics and recommendations updated.")
    with t2:
        subj = st.selectbox("Subject", names, key="a_subj")
        subject_id = int(subjects.loc[subjects.subject == subj, "subject_id"].iloc[0])
        topics = repo.get_topics(subject_id)
        with st.form("activity_form", clear_on_submit=True):
            topic = st.selectbox("Topic", topics.topic.tolist())
            c = st.columns(3)
            atype = c[0].selectbox("Activity type", ACTIVITY_TYPES)
            dur = c[1].number_input("Duration (min)", min_value=1.0, max_value=600.0, value=30.0, step=5.0)
            done = c[2].checkbox("Completed", value=True)
            adate = st.date_input("Date", value=date.today(), max_value=date.today(), key="adate")
            if st.form_submit_button("Save activity", type="primary"):
                tid = int(topics.loc[topics.topic == topic, "topic_id"].iloc[0])
                repo.add_activity(sid, subject_id, tid, atype, dur, done, adate)
                _refresh(sid)
                st.success(f"Saved {dur:g} min of {atype.lower()} on {topic}.")
    st.subheader("Recent entries")
    q = repo.get_quizzes(sid).tail(8).iloc[::-1]
    if q.empty:
        st.caption("Nothing logged yet.")
    else:
        table(q[["quiz_date", "subject", "topic", "score_pct"]].assign(quiz_date=q.quiz_date.dt.date).round(1))
