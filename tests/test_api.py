"""Unit tests for SecureTaskAPI."""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from main import app, TASKS


@pytest.fixture(autouse=True)
def clear_tasks():
    """Reset in-memory store before every test."""
    TASKS.clear()
    yield
    TASKS.clear()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "healthy"


# ── Create ─────────────────────────────────────────────────────────────────────

def test_create_task_success(client):
    r = client.post("/tasks", json={"title": "Buy milk", "description": "2% please"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "id" in data


def test_create_task_missing_title(client):
    r = client.post("/tasks", json={"description": "No title here"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_create_task_empty_body(client):
    r = client.post("/tasks", data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_create_task_title_too_long(client):
    r = client.post("/tasks", json={"title": "x" * 121})
    assert r.status_code == 400


# ── Input sanitisation ─────────────────────────────────────────────────────────

def test_xss_characters_stripped(client):
    r = client.post("/tasks", json={"title": "<script>alert(1)</script>Task"})
    assert r.status_code == 201
    assert "<script>" not in r.get_json()["title"]


def test_sql_injection_chars_stripped(client):
    r = client.post("/tasks", json={"title": "'; DROP TABLE tasks; --"})
    assert r.status_code == 201
    title = r.get_json()["title"]
    assert "'" not in title
    assert ";" not in title


# ── List & Get ─────────────────────────────────────────────────────────────────

def test_list_tasks_empty(client):
    r = client.get("/tasks")
    assert r.status_code == 200
    assert r.get_json()["count"] == 0


def test_list_tasks_after_create(client):
    client.post("/tasks", json={"title": "Task A"})
    client.post("/tasks", json={"title": "Task B"})
    r = client.get("/tasks")
    assert r.get_json()["count"] == 2


def test_get_task_not_found(client):
    r = client.get("/tasks/nonexistent-id")
    assert r.status_code == 404


def test_get_task_success(client):
    create = client.post("/tasks", json={"title": "Specific task"}).get_json()
    r = client.get(f"/tasks/{create['id']}")
    assert r.status_code == 200
    assert r.get_json()["title"] == "Specific task"


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_task_status(client):
    task_id = client.post("/tasks", json={"title": "Do laundry"}).get_json()["id"]
    r = client.put(f"/tasks/{task_id}", json={"status": "done"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "done"


def test_update_task_invalid_status(client):
    task_id = client.post("/tasks", json={"title": "Test"}).get_json()["id"]
    r = client.put(f"/tasks/{task_id}", json={"status": "flying"})
    assert r.status_code == 400


def test_update_nonexistent_task(client):
    r = client.put("/tasks/no-such-id", json={"title": "Ghost"})
    assert r.status_code == 404


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_task(client):
    task_id = client.post("/tasks", json={"title": "Delete me"}).get_json()["id"]
    r = client.delete(f"/tasks/{task_id}")
    assert r.status_code == 200
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_delete_nonexistent_task(client):
    r = client.delete("/tasks/no-such-id")
    assert r.status_code == 404


# ── Search ─────────────────────────────────────────────────────────────────────

def test_search_no_query(client):
    r = client.get("/tasks/search")
    assert r.status_code == 400


def test_search_finds_match(client):
    client.post("/tasks", json={"title": "Buy groceries"})
    client.post("/tasks", json={"title": "Call dentist"})
    r = client.get("/tasks/search?q=groceries")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 1
    assert data["results"][0]["title"] == "Buy groceries"


def test_search_no_match(client):
    client.post("/tasks", json={"title": "Some task"})
    r = client.get("/tasks/search?q=zebra")
    assert r.get_json()["count"] == 0
