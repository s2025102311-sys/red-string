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


def _community_page_client(tmp_path):
    community = {"id": 1, "name": "Naga Donors", "description": "Hi", "created_by": 1, "member_count": 3}

    def member(uid, username, name, blood, loc, public):
        return {"u_id": uid, "username": username, "email": f"{username}@mail.com", "p_id": uid,
                "p_full_name": name, "p_location": loc, "p_sex": None, "p_birthdate": None,
                "p_blood_type": blood, "p_bio": None, "p_picture": "default.jpg", "p_is_public": public}

    conn = FakeConnection([
        ("WHERE c.id", [community]),
        ("FROM community_members cm JOIN users", [
            member(1, "maria", "Maria Santos", "O+", "Naga City", True),
            member(2, "jose", "Jose Reyes", "A-", "Legazpi", True),
            member(3, "hiddenone", "Hidden One", "B+", "Manila", False)]),
    ])
    app = create_app(conn_factory=lambda: conn, upload_folder=str(tmp_path))
    return app.test_client()


def test_community_page_shows_search_box_and_all_members(tmp_path):
    html = _community_page_client(tmp_path).get("/communities/1").get_data(as_text=True)
    assert 'name="q"' in html and "Maria Santos" in html and "Jose Reyes" in html
    assert html.count("hidden>") <= 3                       # nothing filtered out without a search


def test_community_search_hides_non_matches_without_javascript(tmp_path):
    html = _community_page_client(tmp_path).get("/communities/1?q=santos").get_data(as_text=True)
    assert "Showing 1 of 3 members" in html
    jose_card = html[html.index('href="/u/jose"'):]
    assert "hidden" in jose_card.split(">")[0] + jose_card.split(">")[1]      # Jose's card is hidden


def test_community_search_never_exposes_private_member(tmp_path):
    html = _community_page_client(tmp_path).get("/communities/1?q=hiddenone").get_data(as_text=True)
    assert "Showing 0 of 3 members" in html and "No members match" in html
    assert "Hidden One" not in html and "hiddenone" not in html.replace('value="hiddenone"', "").replace(
        '<span id="member-search-term">hiddenone</span>', "")
