import re
import sqlite3

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE": str(tmp_path / "test.sqlite3"),
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret",
    })


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf(response):
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def login(client):
    response = client.get("/login")
    return client.post("/login", data={
        "username": "admin", "password": "secret", "csrf_token": csrf(response)
    })


def create_url(client, original_url):
    dashboard = client.get("/")
    return client.post("/urls", data={
        "original_url": original_url,
        "csrf_token": csrf(dashboard),
    })


def test_dashboard_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.location


def test_theme_controls_and_script(client):
    login_page = client.get("/login")
    assert "data-theme-selector" in login_page.text
    assert login_page.text.index("theme.js") < login_page.text.index("style.css")

    theme_script = client.get("/static/theme.js")
    assert theme_script.status_code == 200
    assert "prefers-color-scheme: dark" in theme_script.text
    assert "localStorage" in theme_script.text

    login(client)
    assert "data-theme-selector" in client.get("/").text


def test_create_follow_count_and_delete(client, app):
    assert login(client).status_code == 302
    response = create_url(client, "example.com/page")
    assert response.status_code == 303
    assert "created=" in response.location
    assert "status=created" in response.location
    result_page = client.get(response.location)
    assert "새 링크가 만들어졌습니다" in result_page.text
    assert "data-copy=" in result_page.text
    assert "새 링크가 만들어졌습니다" in client.get(response.location).text

    with sqlite3.connect(app.config["DATABASE"]) as db:
        row = db.execute("SELECT id, code, original_url, clicks FROM urls").fetchone()
        assert row[2] == "https://example.com/page"

    response = client.get(f"/s/{row[1]}")
    assert response.status_code == 302
    assert response.location == "https://example.com/page"

    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT clicks FROM urls").fetchone()[0] == 1

    dashboard = client.get("/")
    response = client.post(f"/urls/{row[0]}/delete", data={"csrf_token": csrf(dashboard)})
    assert response.status_code == 302
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM urls").fetchone()[0] == 0


def test_rejects_unsafe_url_and_bad_csrf(client):
    login(client)
    dashboard = client.get("/")
    client.post("/urls", data={"original_url": "javascript:alert(1)", "csrf_token": csrf(dashboard)})
    assert "올바른" in client.get("/").text
    assert client.post("/urls", data={"original_url": "https://example.com", "csrf_token": "bad"}).status_code == 400


def test_allows_custom_protocol(client, app):
    login(client)
    custom_url = "obsidian://open?vault=Notes&file=Inbox"
    response = create_url(client, custom_url)
    assert response.status_code == 303

    with sqlite3.connect(app.config["DATABASE"]) as db:
        code, stored_url = db.execute(
            "SELECT code, original_url FROM urls"
        ).fetchone()
    assert stored_url == custom_url
    response = client.get(f"/s/{code}")
    assert response.status_code == 302
    assert response.location == custom_url


def test_reuses_existing_short_url(client, app):
    login(client)
    original_url = "https://example.com/same"
    first = create_url(client, original_url)
    second = create_url(client, original_url)

    assert first.status_code == 303
    assert second.status_code == 303
    assert "created=" in second.location
    assert "status=existing" in second.location
    result_page = client.get(second.location)
    assert "이미 등록된 링크입니다" in result_page.text

    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM urls").fetchone()[0] == 1
