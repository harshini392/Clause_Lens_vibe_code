"""Pytest fixtures and test setup for ClauseLens."""
import os
import shutil
import tempfile
from pathlib import Path
import pytest

# Ensure test runs local with test config
os.environ["DEBUG"] = "false"
os.environ["NEMOTRON_ENABLED"] = "false"

import config
import database
from app import app, CSRF_COOKIE_NAME


@pytest.fixture(scope="session")
def sample_dir():
    """Path to sample contracts directory."""
    path = Path(__file__).resolve().parent.parent / "sample_contracts"
    assert path.exists(), "Sample directory must exist."
    return path


@pytest.fixture
def test_db():
    """Create a clean isolated SQLite database for each test."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_clauselens.db")
    orig_path = config.DATABASE_PATH
    config.DATABASE_PATH = db_path

    database.init_db(db_path)
    database.seed_demo_policies(db_path, overwrite=True)

    yield db_path

    config.DATABASE_PATH = orig_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(test_db):
    """Flask test client configured with CSRF token generation helper."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        # Obtain initial CSRF cookie and token
        res = c.get("/api/csrf")
        token = res.get_json()["token"]

        class CsrfClientWrapper:
            def __init__(self, raw_client, csrf_token):
                self.raw = raw_client
                self.token = csrf_token

            def get(self, *args, **kwargs):
                return self.raw.get(*args, **kwargs)

            def post(self, *args, **kwargs):
                headers = kwargs.get("headers", {})
                if "X-CSRF-Token" not in headers:
                    headers["X-CSRF-Token"] = self.token
                kwargs["headers"] = headers
                return self.raw.post(*args, **kwargs)

            def put(self, *args, **kwargs):
                headers = kwargs.get("headers", {})
                if "X-CSRF-Token" not in headers:
                    headers["X-CSRF-Token"] = self.token
                kwargs["headers"] = headers
                return self.raw.put(*args, **kwargs)

            def delete(self, *args, **kwargs):
                headers = kwargs.get("headers", {})
                if "X-CSRF-Token" not in headers:
                    headers["X-CSRF-Token"] = self.token
                kwargs["headers"] = headers
                return self.raw.delete(*args, **kwargs)

        yield CsrfClientWrapper(c, token)
