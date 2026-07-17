"""Tests for the web dashboard."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TELEGRAM_API_ID", "12345678")
os.environ.setdefault("TELEGRAM_API_HASH", "test_api_hash_for_unit_tests")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Return a TestClient with an isolated database."""
    monkeypatch.setenv("SENTRI_DATA_DIR", str(tmp_path / "data"))
    from sentri.config.settings import get_settings

    get_settings.cache_clear()

    from sentri.web.app import create_app

    return TestClient(create_app())


class TestWebDashboard:
    """Tests for web pages and API."""

    def test_dashboard_loads(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "Sentri" in response.text
        assert "Dashboard" in response.text

    def test_api_status(self, client: TestClient) -> None:
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "authenticated" in data
        assert "groups_total" in data
        assert data["watch_running"] is False

    def test_add_and_list_groups(self, client: TestClient) -> None:
        create = client.post(
            "/api/groups",
            json={"chat_id": -100123, "title": "Test Group", "watch_mode": "admins_only"},
        )
        assert create.status_code == 200
        assert create.json()["title"] == "Test Group"

        listing = client.get("/api/groups")
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    def test_duplicate_group_rejected(self, client: TestClient) -> None:
        payload = {"chat_id": -100999, "title": "G"}
        client.post("/api/groups", json=payload)
        dup = client.post("/api/groups", json=payload)
        assert dup.status_code == 409

    def test_add_user_by_id(self, client: TestClient) -> None:
        group = client.post("/api/groups", json={"chat_id": -1001, "title": "G"}).json()
        response = client.post(
            f"/api/groups/{group['id']}/users",
            json={"user_id": 42, "display_name": "Alice", "username": "alice"},
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == 42

        users = client.get(f"/api/groups/{group['id']}/users")
        assert len(users.json()) == 1

    def test_set_destination(self, client: TestClient) -> None:
        response = client.post(
            "/api/config/destination",
            json={"chat_id": -4999, "title": "My Dest"},
        )
        assert response.status_code == 200
        assert response.json()["destination_chat_id"] == -4999

    def test_watch_start_requires_auth(self, client: TestClient) -> None:
        client.post("/api/groups", json={"chat_id": -100, "title": "G"})
        client.post("/api/config/destination", json={"chat_id": -200, "title": "D"})
        response = client.post("/api/watch/start")
        assert response.status_code == 400

    def test_web_token_protection(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("SENTRI_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("SENTRI_WEB_TOKEN", "secret123")
        from sentri.config.settings import get_settings

        get_settings.cache_clear()

        from sentri.web.app import create_app

        protected = TestClient(create_app())
        assert protected.get("/").status_code == 401
        assert protected.get("/?token=secret123").status_code == 200
        get_settings.cache_clear()
