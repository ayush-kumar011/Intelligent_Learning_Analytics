"""Entry point:  streamlit run app.py"""
import time

import streamlit as st

from config import settings
from services import auth, bootstrap
from utils import validation
from utils.ui import inject_css

st.set_page_config(page_title=settings.APP_NAME, page_icon=":material/school:", layout="wide")
inject_css()


@st.cache_resource(show_spinner="First run: generating the synthetic cohort and training models (about 30 s)...")
def _boot() -> bool:
    bootstrap.ensure_ready()
    return True


def auth_screen():
    st.title(settings.APP_NAME)
    st.caption("Personalised learning recommendations from performance and engagement data.")
    tab_in, tab_up = st.tabs(["Log in", "Register as student"])
    with tab_in:
        locked = st.session_state.get("locked_until", 0) - time.time()
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            go = st.form_submit_button("Log in", type="primary")
        if go:
            if locked > 0:
                st.error(f"Too many failed attempts. Try again in {int(locked)} s.")
            elif not u or not p:
                st.error("Enter both username and password.")
            else:
                user = auth.authenticate(u, p)
                if user:
                    st.session_state.pop("fails", None)
                    st.session_state["user"] = user
                    st.rerun()
                st.session_state["fails"] = st.session_state.get("fails", 0) + 1
                if st.session_state["fails"] >= 5:
                    st.session_state["locked_until"] = time.time() + 30
                    st.session_state["fails"] = 0
                st.error("Invalid username or password.")
        st.info(f"Demo accounts - student: `{settings.DEMO_STUDENT_USERNAME}` / `{settings.DEMO_STUDENT_PASSWORD}` (synthetic data); "
                f"admin: `{settings.ADMIN_USERNAME}` / `{settings.ADMIN_PASSWORD}`.")
    with tab_up:
        with st.form("register_form"):
            name = st.text_input("Full name")
            c = st.columns(2)
            username, email = c[0].text_input("Username"), c[1].text_input("Email")
            c = st.columns(2)
            pw, pw2 = c[0].text_input("Password", type="password"), c[1].text_input("Confirm password", type="password")
            c = st.columns(3)
            age = c[0].number_input("Age", 10, 100, value=None, step=1)
            level = c[1].selectbox("Grade level", settings.GRADE_LEVELS)
            hours = c[2].number_input("Study hours / week", 0.0, 100.0, value=None, step=0.5)
            goal = st.text_area("Learning goal (optional)")
            if st.form_submit_button("Create account", type="primary"):
                if pw != pw2:
                    st.error("Passwords do not match.")
                else:
                    ok, errs, _ = auth.register_student(username, email, pw, name, age, level, hours, goal)
                    if ok:
                        st.success("Account created. Switch to the Log in tab.")
                    else:
                        for e in errs:
                            st.error(e)


_boot()
user = st.session_state.get("user")
if not user:
    auth_screen()
    st.stop()

from pages import (admin_content, admin_models, admin_overview, admin_students, reports,  # noqa: E402
                   student_dashboard, student_log, student_profile, student_recommendations)

P = st.Page
if user["role"] == "admin":
    nav = st.navigation({"Admin": [
        P(admin_overview.render, title="Overview", icon=":material/monitoring:", url_path="overview", default=True),
        P(admin_students.render, title="Students", icon=":material/groups:", url_path="students"),
        P(admin_models.render, title="Model Lab", icon=":material/psychology:", url_path="models"),
        P(admin_content.render, title="Materials", icon=":material/menu_book:", url_path="materials"),
        P(reports.render, title="Reports", icon=":material/description:", url_path="reports"),
        P(student_profile.render, title="Account", icon=":material/person:", url_path="account")]})
else:
    nav = st.navigation({"Learning": [
        P(student_dashboard.render, title="Dashboard", icon=":material/dashboard:", url_path="dashboard", default=True),
        P(student_recommendations.render, title="Recommendations", icon=":material/lightbulb:", url_path="recommendations"),
        P(student_log.render, title="Log Learning", icon=":material/edit_note:", url_path="log"),
        P(reports.render, title="Reports", icon=":material/description:", url_path="reports"),
        P(student_profile.render, title="Profile", icon=":material/person:", url_path="profile")]})
with st.sidebar:
    st.markdown(f"**{user['username']}**  \n{user['role'].title()}")
    if st.button("Log out"):
        st.session_state.clear()
        st.rerun()
nav.run()
