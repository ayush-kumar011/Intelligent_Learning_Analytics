"""Runs the real Streamlit script with streamlit.testing (no browser): login, page rendering, form submits."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from config import settings
from database import repository as repo

ROOT = Path(__file__).resolve().parent.parent
STUDENT_PAGES = ["student_dashboard", "student_recommendations", "student_log", "student_profile", "reports"]
ADMIN_PAGES = ["admin_overview", "admin_students", "admin_models", "admin_content", "reports", "student_profile"]


def _page(module, user):
    at = AppTest.from_string(f"from views import {module}\n{module}.render()", default_timeout=90)
    at.session_state["user"] = user
    return at.run()


def _btn(at, label):
    return next(b for b in at.button if b.label == label)


def test_login_page_and_bad_credentials():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception and at.title[0].value == settings.APP_NAME
    at.text_input[0].set_value("demo_student")
    at.text_input[1].set_value("wrong-password")
    _btn(at, "Log in").click().run()
    assert any("Invalid" in e.value for e in at.error)


@pytest.mark.parametrize("who,title", [(("demo_student", settings.DEMO_STUDENT_PASSWORD), "My Learning Dashboard"),
                                       ((settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD), "Admin Overview")])
def test_login_routes_by_role(who, title):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.text_input[0].set_value(who[0])
    at.text_input[1].set_value(who[1])
    _btn(at, "Log in").click().run()
    assert not at.exception and at.title[0].value == title


def test_registration_form_creates_account():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    labels = {t.label: t for t in at.text_input}
    inputs = list(at.text_input)
    # register tab inputs: name, username, email, password, confirm (after the 2 login inputs)
    name, user, email, pw, pw2 = inputs[2:7]
    name.set_value("UI Tester"); user.set_value("ui_tester_1"); email.set_value("ui1@x.com"); pw.set_value("Passw0rdX"); pw2.set_value("Passw0rdX")
    _btn(at, "Create account").click().run()
    assert not at.exception and repo.get_user("ui_tester_1") is not None


@pytest.mark.parametrize("module", STUDENT_PAGES)
def test_student_pages_render(module):
    at = _page(module, {"id": 1, "username": "demo_student", "role": "student", "student_id": 1})
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("module", ADMIN_PAGES)
def test_admin_pages_render(module):
    at = _page(module, {"id": 1, "username": "admin", "role": "admin", "student_id": None})
    assert not at.exception, [e.value for e in at.exception]


def test_role_separation():
    at = _page("admin_overview", {"id": 5, "username": "x", "role": "student", "student_id": 1})
    assert any("not authorised" in e.value for e in at.error)
    at = _page("student_dashboard", {"id": 1, "username": "admin", "role": "admin", "student_id": None})
    assert any("not authorised" in e.value for e in at.error)


def test_log_quiz_form_persists_and_updates(new_student):
    sid = new_student["student_id"]
    at = _page("student_log", new_student)
    at.number_input[0].set_value(45.0)  # score
    _btn(at, "Save quiz result").click().run()
    assert not at.exception and any("Saved" in s.value for s in at.success)
    assert len(repo.get_quizzes(sid)) == 1
    at = _page("student_log", new_student)
    at.number_input[0].set_value(150.0)  # exceeds max -> rejected
    _btn(at, "Save quiz result").click().run()
    assert any("cannot exceed" in e.value for e in at.error) and len(repo.get_quizzes(sid)) == 1


def test_recommendation_buttons_work(new_student):
    sid = new_student["student_id"]
    at = _page("student_recommendations", new_student)
    assert not at.exception and len(repo.get_recommendations(sid)) > 0
    before = len(repo.get_recommendations(sid))
    next(b for b in at.button if b.label == "Done").click().run()
    assert len(repo.get_recommendations(sid)) == before - 1
