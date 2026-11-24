import streamlit as st

from analytics import metrics
from views.student_dashboard import render_student_analytics
from recommendations import engine
from utils.ui import require_role, risk_badge, table


def render():
    require_role("admin")
    st.title("Students")
    t = metrics.students_table()
    c = st.columns([2, 1, 1, 1])
    q = c[0].text_input("Search name / username")
    risk = c[1].selectbox("Risk", ["All", "High", "Medium", "Low"])
    seg = c[2].selectbox("Segment", ["All"] + sorted(t.segment.dropna().unique()))
    src = c[3].selectbox("Source", ["All", "real", "synthetic"])
    if q:
        t = t[t.full_name.str.contains(q, case=False, na=False) | t.username.fillna("").str.contains(q, case=False)]
    if risk != "All":
        t = t[t.risk_level == risk]
    if seg != "All":
        t = t[t.segment == seg]
    if src != "All":
        t = t[t.source == src]
    st.caption(f"{len(t)} students")
    table(t[["student_id", "full_name", "username", "source", "grade_level", "avg_score", "overall_predicted", "risk_level", "segment", "quizzes", "hours"]].round(1))
    if t.empty:
        return
    st.divider()
    pick = st.selectbox("Inspect student", t.student_id.tolist(), format_func=lambda i: f"#{i} - {t.set_index('student_id').at[i, 'full_name']}")
    row = t.set_index("student_id").loc[pick]
    st.subheader(row.full_name)
    st.markdown(f"{risk_badge(row.risk_level)} &nbsp; <span class='badge b-seg'>{row.segment or 'No segment'}</span> &nbsp; {row.source}", unsafe_allow_html=True)
    render_student_analytics(int(pick))
    if st.button("Preview this student's recommendations"):
        recs = engine.generate(int(pick), persist=False)
        for r in recs[:10]:
            st.markdown(f"- **{r['title']}** - {r['detail']}")
