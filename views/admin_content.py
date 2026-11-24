import streamlit as st

from config.curriculum import LEVELS, MATERIAL_TYPES
from database import repository as repo
from utils.ui import require_role, table


def render():
    require_role("admin")
    st.title("Learning Materials")
    st.caption("The seeded catalogue has placeholder titles without links. Add real resources here; the recommendation engine uses them immediately.")
    subjects = repo.get_subjects()
    subj = st.selectbox("Subject", subjects.subject.tolist())
    topics = repo.get_topics(int(subjects.loc[subjects.subject == subj, "subject_id"].iloc[0]))
    with st.form("material_form", clear_on_submit=True):
        topic = st.selectbox("Topic", topics.topic.tolist())
        title = st.text_input("Title")
        c = st.columns(3)
        mtype = c[0].selectbox("Type", MATERIAL_TYPES)
        level = c[1].selectbox("Level", LEVELS)
        mins = c[2].number_input("Estimated minutes", 1, 600, 30)
        url = st.text_input("URL (optional, must start with http)")
        desc = st.text_area("Description (optional)")
        if st.form_submit_button("Add material", type="primary"):
            if not title.strip():
                st.error("Title is required.")
            elif url and not url.lower().startswith(("http://", "https://")):
                st.error("URL must start with http:// or https://")
            else:
                repo.add_material(int(topics.loc[topics.topic == topic, "topic_id"].iloc[0]), title.strip(), mtype, level, url.strip(), int(mins), desc.strip())
                st.success("Material added.")
    mats = repo.get_materials()
    table(mats[mats.subject == subj][["topic", "title", "material_type", "level", "est_minutes", "url"]])
