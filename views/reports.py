import streamlit as st

from analytics import metrics
from database import repository as repo
from recommendations import engine
from utils import reports
from utils.ui import current_user, table


def render():
    user = current_user()
    st.title("Reports")
    if user["role"] == "admin":
        students = repo.list_students()
        label = students.apply(lambda r: f"{r.full_name} (#{r.student_id}{', synthetic' if r.is_synthetic else ''})", axis=1)
        pick = st.selectbox("Student", label.tolist())
        sid = int(students.student_id.iloc[label.tolist().index(pick)])
    else:
        sid = user["student_id"]
    if repo.get_recommendations(sid, None).empty:
        engine.generate(sid)
    d = reports.report_data(sid)
    ov = d["overview"]
    if ov["quizzes"] == 0:
        st.info("No quiz data yet - the report will be available once results are logged.")
        return
    st.subheader(d["student"]["full_name"])
    st.write(f"Average **{ov['avg_score']:.1f}%** over **{ov['quizzes']}** quizzes, **{ov['total_hours']:.1f} h** logged study time. "
             f"Risk: **{ov['risk'] or 'n/a'}**, segment: **{ov['segment'] or 'n/a'}**.")
    st.markdown("**Subject-wise analytics**")
    table(d["subjects"].drop(columns=["subject_id"]).round(1))
    st.markdown("**Weakest topics**")
    table(d["weak"][["subject", "topic", "mastery", "attempts", "peer_avg"]].round(1)) if len(d["weak"]) else st.caption("None below 70%.")
    st.markdown("**Improvement suggestions**")
    for r in d["recs"].head(8).itertuples():
        st.markdown(f"- **{r.title}** - {r.detail}")
    c = st.columns(4)
    c[0].download_button("PDF report", reports.student_pdf(d), f"report_student_{sid}.pdf", "application/pdf", type="primary")
    c[1].download_button("Subjects CSV", reports.subjects_csv(d), f"subjects_{sid}.csv", "text/csv")
    c[2].download_button("Topics CSV", reports.topics_csv(d), f"topics_{sid}.csv", "text/csv")
    c[3].download_button("Suggestions CSV", reports.recommendations_csv(d), f"suggestions_{sid}.csv", "text/csv")
