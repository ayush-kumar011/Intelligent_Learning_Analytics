import streamlit as st

from analytics import metrics
from utils import charts
from utils.ui import plot, require_role, risk_badge, table


def render_student_analytics(student_id: int) -> None:
    """Shared by the student dashboard and the admin's per-student drill-down."""
    ov = metrics.student_overview(student_id)
    if ov["quizzes"] == 0:
        st.info("No quiz results recorded yet. Use **Log Learning** to add quizzes and study activities.")
        return
    c = st.columns(5)
    c[0].metric("Average score", f"{ov['avg_score']:.1f}%")
    c[1].metric("Quizzes taken", ov["quizzes"])
    c[2].metric("Study time", f"{ov['total_hours']:.1f} h")
    c[3].metric("Completion rate", "-" if ov["completion_rate"] is None else f"{ov['completion_rate']:.0f}%")
    c[4].metric("Model projection", "-" if ov["predicted"] is None else f"{ov['predicted']:.0f}%",
                help="Predicted average of upcoming quizzes (needs >= 3 quizzes in a subject).")
    st.markdown(f"{risk_badge(ov['risk'])} &nbsp; <span class='badge b-seg'>{ov['segment'] or 'No segment yet'}</span>", unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["Subjects", "Progress & time", "Topic mastery", "Assessment history"])
    with t1:
        sp = metrics.subject_performance(student_id)
        plot(charts.subject_bar(sp))
        view = sp.rename(columns={"avg_score": "Avg %", "quizzes": "Quizzes", "minutes": "Minutes", "cohort_avg": "Cohort %",
                                  "predicted_score": "Projected %", "predicted_category": "Category"})
        table(view.drop(columns=["subject_id"]).round(1))
    with t2:
        plot(charts.score_timeline(metrics.score_timeline(student_id)))
        wt = metrics.weekly_time(student_id)
        if len(wt):
            plot(charts.weekly_time(wt))
        else:
            st.caption("No learning activities logged yet.")
    with t3:
        tm = metrics.topic_mastery(student_id)
        plot(charts.topic_heatmap(tm))
        weak = tm[(tm.attempts > 0) & (tm.mastery < 70)].sort_values("mastery")
        st.subheader("Learning gaps (mastery below 70%)")
        if weak.empty:
            st.success("No topics below the 70% target.")
        else:
            table(weak[["subject", "topic", "mastery", "attempts", "peer_avg", "gap_vs_peers"]].round(1))
    with t4:
        h = metrics.assessment_history(student_id)
        subjects = ["All"] + sorted(h.subject.unique())
        pick = st.selectbox("Subject", subjects, key=f"hist_subject_{student_id}")
        if pick != "All":
            h = h[h.subject == pick]
        h = h.assign(quiz_date=h.quiz_date.dt.date).round(1)
        table(h.rename(columns={"quiz_date": "Date", "subject": "Subject", "topic": "Topic", "score_pct": "Score %", "time_taken_min": "Minutes"}))


def render():
    user = require_role("student")
    st.title("My Learning Dashboard")
    render_student_analytics(user["student_id"])
