import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="la_test_")
os.environ["LA_DB_PATH"] = str(Path(_TMP) / "test.db")
os.environ["LA_MODEL_DIR"] = str(Path(_TMP) / "models")
os.environ["LA_N_STUDENTS"] = "120"
os.environ["LA_PBKDF2_ITERS"] = "2000"  # fast hashing for tests only

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def system():
    from services import bootstrap
    bootstrap.ensure_ready()
    yield


@pytest.fixture()
def new_student():
    import uuid
    from services import auth
    u = "t_" + uuid.uuid4().hex[:10]
    ok, errs, user = auth.register_student(u, f"{u}@x.com", "Passw0rdX", "Test Student", 20, "Year 2", 10, None)
    assert ok, errs
    return user
