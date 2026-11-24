from config import settings
from database import repository as repo
from services import auth


def test_register_login_roundtrip(new_student):
    assert new_student["role"] == "student" and new_student["student_id"]
    u = auth.authenticate(new_student["username"], "Passw0rdX")
    assert u and u["student_id"] == new_student["student_id"]
    assert auth.authenticate(new_student["username"], "wrong") is None


def test_password_is_hashed_and_salted(new_student):
    h = repo.get_user(new_student["username"])["password_hash"]
    assert "Passw0rdX" not in h and h.startswith("pbkdf2_sha256$")
    assert auth.hash_password("same") != auth.hash_password("same")


def test_validation_and_duplicates(new_student):
    assert auth.register_student("a", "bad", "short", "", 5)[0] is False
    ok, errs, _ = auth.register_student(new_student["username"], "other@x.com", "Passw0rdX", "Dup", 20)
    assert not ok and "username" in errs[0]


def test_admin_and_demo_roles_and_synthetic_cannot_login():
    assert auth.authenticate(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)["role"] == "admin"
    assert auth.authenticate(settings.DEMO_STUDENT_USERNAME, settings.DEMO_STUDENT_PASSWORD)["role"] == "student"
    assert auth.authenticate("nobody", "x") is None


def test_change_password(new_student):
    ok, _ = auth.change_password(new_student["id"], new_student["username"], "Passw0rdX", "NewPassw0rd9")
    assert ok and auth.authenticate(new_student["username"], "NewPassw0rd9")
    assert not auth.change_password(new_student["id"], new_student["username"], "bad", "NewPassw0rd9")[0]
