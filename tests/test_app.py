"""Front-end smoke tests: Flask test client with a fake database (no MySQL)."""
import pytest

from app import create_app
from registry.exceptions import DatabaseError
from tests.fakes import FakeConnection


@pytest.fixture
def client(tmp_path):
    conn = FakeConnection()
    app = create_app(conn_factory=lambda: conn, upload_folder=str(tmp_path))
    app.config["TESTING"] = False        # use the real error handlers, like production
    return app.test_client(), conn


def messages(client):
    with client.session_transaction() as session:
        return [m for _, m in session.get("_flashes", [])]


def test_login_page_renders(client):
    c, _ = client
    assert c.get("/login").status_code == 200


def test_validation_error_becomes_friendly_flash_not_a_crash(client):
    c, conn = client
    response = c.post("/register", data={"username": "ab", "email": "x@y.com",
                                         "password": "password123", "confirm_password": "password123"})
    assert response.status_code == 302
    assert "Username must be 3-30 characters" in messages(c)[0]
    assert conn.commits == 0


def test_wrong_login_shows_message(client):
    c, _ = client
    c.post("/login", data={"email": "nobody@mail.com", "password": "whatever1"})
    assert messages(c) == ["Invalid email or password."]


def test_database_down_shows_error_page_not_traceback():
    def broken():
        raise DatabaseError("Cannot reach the database right now. Please try again later.")
    app = create_app(conn_factory=broken)
    response = app.test_client().get("/communities")
    assert response.status_code == 503
    assert b"Cannot reach the database" in response.data


def test_login_required_redirects_to_login(client):
    c, _ = client
    response = c.get("/profile")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_unknown_page_is_a_normal_404(client):
    c, _ = client
    assert c.get("/nope").status_code == 404
