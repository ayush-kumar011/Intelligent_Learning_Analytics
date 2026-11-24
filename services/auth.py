"""Registration, authentication and password handling (PBKDF2-HMAC-SHA256, per-user salt)."""
import hashlib
import hmac
import secrets
import sqlite3

from config import settings
from database import db, repository as repo
from utils import validation as v


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or settings.pbkdf2_iterations()
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
        return hmac.compare_digest(check, digest)
    except (ValueError, AttributeError):
        return False


def register_student(username, email, password, full_name, age=None, grade_level=None,
                     study_hours_per_week=None, learning_goal=None):
    """Returns (ok, errors, user_dict). Creates the user and student profile atomically."""
    username, email, full_name = (username or "").strip(), (email or "").strip(), (full_name or "").strip()
    errs = (v.check_username(username) + v.check_email(email) + v.check_password(password)
            + v.check_range("Age", age, 10, 100) + v.check_range("Weekly study hours", study_hours_per_week, 0, 100))
    if not full_name:
        errs.append("Full name is required.")
    if errs:
        return False, errs, None
    try:
        with db.get_conn() as c:
            uid = c.execute("INSERT INTO users(username,email,password_hash,role) VALUES (?,?,?,'student')",
                            (username, email, hash_password(password))).lastrowid
            sid = c.execute(
                "INSERT INTO students(user_id,full_name,age,grade_level,study_hours_per_week,learning_goal,is_synthetic) "
                "VALUES (?,?,?,?,?,?,0)", (uid, full_name, age, grade_level, study_hours_per_week, learning_goal or None)
            ).lastrowid
    except sqlite3.IntegrityError as e:
        field = "email" if "email" in str(e).lower() else "username"
        return False, [f"That {field} is already registered."], None
    return True, [], {"id": uid, "username": username, "role": "student", "student_id": sid}


def authenticate(username: str, password: str):
    """Returns user dict or None. Synthetic accounts have no password hash and can never log in."""
    user = repo.get_user((username or "").strip())
    if not user or not verify_password(password or "", user["password_hash"]):
        return None
    student = repo.get_student_by_user(user["id"]) if user["role"] == "student" else None
    return {"id": user["id"], "username": user["username"], "role": user["role"],
            "student_id": student["id"] if student else None}


def change_password(user_id: int, username: str, current: str, new: str):
    if not authenticate(username, current):
        return False, ["Current password is incorrect."]
    errs = v.check_password(new)
    if errs:
        return False, errs
    repo.update_password(user_id, hash_password(new))
    return True, []


def ensure_admin() -> None:
    if not repo.get_user(settings.ADMIN_USERNAME):
        db.execute("INSERT INTO users(username,email,password_hash,role) VALUES (?,?,?,'admin')",
                   (settings.ADMIN_USERNAME, "admin@example.local", hash_password(settings.ADMIN_PASSWORD)))
