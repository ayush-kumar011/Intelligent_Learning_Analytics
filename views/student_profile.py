import streamlit as st

from config import settings
from database import repository as repo
from services import auth
from utils import validation as v
from utils.ui import current_user


def _password_form(user):
    st.subheader("Change password")
    with st.form("pw_form", clear_on_submit=True):
        cur = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        conf = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password"):
            if new != conf:
                st.error("New passwords do not match.")
            else:
                ok, errs = auth.change_password(user["id"], user["username"], cur, new)
                st.success("Password updated.") if ok else [st.error(e) for e in errs]


def render():
    user = current_user()
    st.title("Profile")
    if user["role"] == "admin":
        st.write(f"Signed in as **{user['username']}** (administrator).")
        _password_form(user)
        return
    s = repo.get_student(user["student_id"])
    st.caption("Optional fields improve prediction quality; leave blank if unknown (missing values are handled).")
    with st.form("profile_form"):
        name = st.text_input("Full name", s["full_name"])
        c = st.columns(3)
        age = c[0].number_input("Age", 10, 100, value=s["age"], step=1)
        lv = settings.GRADE_LEVELS
        level = c[1].selectbox("Grade level", lv, index=lv.index(s["grade_level"]) if s["grade_level"] in lv else 0)
        hours = c[2].number_input("Study hours / week", 0.0, 100.0, value=s["study_hours_per_week"], step=0.5)
        c = st.columns(3)
        att = c[0].number_input("Attendance %", 0.0, 100.0, value=s["attendance_pct"], step=1.0)
        sleep = c[1].number_input("Sleep hours / night", 0.0, 24.0, value=s["sleep_hours"], step=0.5)
        gpa = c[2].number_input("Previous GPA (0-4)", 0.0, 4.0, value=s["prior_gpa"], step=0.05)
        goal = st.text_area("Learning goal", s["learning_goal"] or "")
        if st.form_submit_button("Save profile", type="primary"):
            errs = [] if name.strip() else ["Full name is required."]
            errs += v.check_range("Age", age, 10, 100)
            if errs:
                [st.error(e) for e in errs]
            else:
                repo.update_student(s["id"], full_name=name.strip(), age=age, grade_level=level, study_hours_per_week=hours,
                                    attendance_pct=att, sleep_hours=sleep, prior_gpa=gpa, learning_goal=goal.strip() or None)
                st.success("Profile saved.")
    _password_form(user)
