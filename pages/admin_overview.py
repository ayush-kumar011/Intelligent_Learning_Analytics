import streamlit as st

from analytics import metrics
from utils import charts
from utils.ui import plot, require_role, table

RISK_COLORS = {"High": "#DC2626", "Medium": "#D97706", "Low": "#059669"}


def render():
    require_role("admin")
    st.title("Admin Overview")
    ov = metrics.cohort_overview()
    c = st.columns(5)
    c[0].metric("Students", ov["students"], help=f"{ov['real']} real registrations, {ov['synthetic']} synthetic demo students")
    c[1].metric("Quizzes recorded", f"{ov['quizzes']:,}")
    c[2].metric("Cohort average", f"{ov['avg_score']:.1f}%" if ov["avg_score"] else "-")
    c[3].metric("High risk", ov["high_risk"])
    c[4].metric("Medium risk", ov["medium_risk"])
    st.caption(f"Data note: {ov['synthetic']} of {ov['students']} students are synthetic (generated), {ov['real']} are real registrations.")
    t = metrics.students_table()
    a, b = st.columns(2)
    with a:
        plot(charts.cohort_hist(metrics.score_distribution()))
    with b:
        plot(charts.cohort_trend(metrics.cohort_trend()))
    a, b, c3 = st.columns(3)
    with a:
        plot(charts.subject_cohort_bar(metrics.cohort_subject_stats()))
    with b:
        plot(charts.distribution_pie(t.risk_level, "Risk levels", RISK_COLORS))
    with c3:
        plot(charts.distribution_pie(t.segment, "Learning segments"))
    st.subheader("Students needing additional support")
    scope = st.radio("Show", ["All students", "Real registrations only"], horizontal=True)
    need = t[t.risk_level == "High"]
    if scope != "All students":
        need = need[need.source == "real"]
    need = need.sort_values("overall_predicted")
    if need.empty:
        st.success("No high-risk students in this view.")
    else:
        table(need[["student_id", "full_name", "source", "avg_score", "overall_predicted", "segment", "quizzes", "hours"]].round(1).rename(
            columns={"overall_predicted": "projected", "hours": "study_hours"}))
    st.subheader("Weakest topics across the cohort")
    table(metrics.weakest_topics_cohort().round(1))
