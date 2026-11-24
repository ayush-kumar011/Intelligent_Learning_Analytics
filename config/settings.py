"""Central configuration. Paths are resolved lazily so tests can override them via env vars."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "Intelligent Learning Analytics"
RANDOM_STATE = 42


def db_path() -> Path:
    return Path(os.environ.get("LA_DB_PATH", BASE_DIR / "data" / "learning_analytics.db"))


def model_dir() -> Path:
    return Path(os.environ.get("LA_MODEL_DIR", BASE_DIR / "models" / "artifacts"))


def n_synthetic_students() -> int:
    return int(os.environ.get("LA_N_STUDENTS", 300))


def pbkdf2_iterations() -> int:
    return int(os.environ.get("LA_PBKDF2_ITERS", 200_000))


ADMIN_USERNAME = os.environ.get("LA_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("LA_ADMIN_PASSWORD", "Admin@12345")  # change for any real deployment
DEMO_STUDENT_USERNAME = "demo_student"
DEMO_STUDENT_PASSWORD = os.environ.get("LA_DEMO_PASSWORD", "Student@123")

MASTERY_TARGET = 70.0
CATEGORIES = ["At Risk", "Average", "Good", "Excellent"]
CATEGORY_BINS = [50, 70, 85]  # <50 At Risk, <70 Average, <85 Good, else Excellent
GRADE_LEVELS = ["Year 1", "Year 2", "Year 3", "Year 4", "Postgraduate"]


def categorize(score: float) -> str:
    for edge, name in zip(CATEGORY_BINS, CATEGORIES):
        if score < edge:
            return name
    return CATEGORIES[-1]
