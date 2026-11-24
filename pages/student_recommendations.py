import html

import streamlit as st

from database import repository as repo
from models import predictor
from recommendations import engine
from utils.ui import require_role, risk_badge

GROUPS = {
    "Learning gaps & materials": ("learning_gap", "material"),
    "Practice quizzes": ("practice_quiz",),
    "Revision schedule": ("revision",),
    "Progress & alerts": ("progress", "subject_alert", "engagement"),
}


def _card(r, tab: str):
    st.markdown(f"<div class='rec-card rec-p{r.priority}'><div class='rec-title'>{html.escape(r.title)}</div>"
                f"<div class='rec-detail'>{html.escape(r.detail)}</div></div>", unsafe_allow_html=True)
    c = st.columns([1, 1, 6])
    if c[0].button("Done", key=f"done_{tab}_{r.rec_id}"):
        repo.set_recommendation_status(r.rec_id, r.student_id_, "done")
        st.rerun()
    if c[1].button("Dismiss", key=f"dis_{tab}_{r.rec_id}"):
        repo.set_recommendation_status(r.rec_id, r.student_id_, "dismissed")
        st.rerun()


def render():
    user = require_role("student")
    sid = user["student_id"]
    st.title("Personalised Recommendations")
    top = st.columns([4, 1])
    ins = repo.get_insights(sid)
    if ins:
        top[0].markdown(f"{risk_badge(ins['risk_level'])} &nbsp; <span class='badge b-seg'>{ins['segment']}</span>", unsafe_allow_html=True)
    if top[1].button("Regenerate", type="primary") or repo.get_recommendations(sid, None).empty:
        with st.spinner("Analysing your records..."):
            if predictor.models_available():
                predictor.refresh([sid])
            engine.generate(sid)
    recs = repo.get_recommendations(sid, "active")
    if recs.empty:
        st.success("No open recommendations - nice work.")
        return
    recs["student_id_"] = sid
    st.caption(f"{len(recs)} open recommendations. Red = urgent, amber = important, green = optional.")
    tabs = st.tabs(["Top priorities"] + list(GROUPS))
    with tabs[0]:
        urgent = recs[recs.priority == 1].head(6)
        if urgent.empty:
            st.info("Nothing urgent right now.")
        for r in urgent.itertuples():
            _card(r, "top")
    for tab, (name, types) in zip(tabs[1:], GROUPS.items()):
        with tab:
            sub = recs[recs.rec_type.isin(types)]
            if sub.empty:
                st.info("Nothing in this category.")
            for r in sub.itertuples():
                _card(r, name)
