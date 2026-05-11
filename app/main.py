"""
SecureTaskAPI - A simple REST API for task management
Features: Task CRUD, user auth simulation, input validation
"""

import logging
import os
import re
import uuid
from datetime import datetime

from flask import Flask, jsonify, request

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)
logger = logging.getLogger("secure-task-api")

app = Flask(__name__)

# In-memory store (simulates a DB)
TASKS: dict = {}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sanitize(text: str, max_len: int = 200) -> str:
    """Strip dangerous characters and enforce length limit."""
    sanitized = re.sub(r"[<>&\"'`;]", "", str(text))
    return sanitized[:max_len]


def _validate_task(data: dict) -> tuple[bool, str]:
    """Return (ok, error_msg)."""
    if not data:
        return False, "Request body is required"
    title = data.get("title", "").strip()
    if not title:
        return False, "Field 'title' is required"
    if len(title) > 120:
        return False, "Title must be ≤ 120 characters"
    return True, ""


# ── Feature 1 – Task CRUD ──────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
def list_tasks():
    logger.info("GET /tasks – returning %d tasks", len(TASKS))
    return jsonify({"tasks": list(TASKS.values()), "count": len(TASKS)})


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    ok, err = _validate_task(data)
    if not ok:
        logger.warning("POST /tasks – validation failed: %s", err)
        return jsonify({"error": err}), 400

    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "title": _sanitize(data["title"]),
        "description": _sanitize(data.get("description", "")),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    TASKS[task_id] = task
    logger.info("POST /tasks – created task %s", task_id)
    return jsonify(task), 201


@app.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        logger.warning("GET /tasks/%s – not found", task_id)
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<task_id>", methods=["PUT"])
def update_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    allowed_statuses = {"pending", "in_progress", "done"}

    if "title" in data:
        ok, err = _validate_task(data)
        if not ok:
            return jsonify({"error": err}), 400
        task["title"] = _sanitize(data["title"])

    if "description" in data:
        task["description"] = _sanitize(data["description"])

    if "status" in data:
        if data["status"] not in allowed_statuses:
            return jsonify({"error": f"status must be one of {allowed_statuses}"}), 400
        task["status"] = data["status"]

    logger.info("PUT /tasks/%s – updated", task_id)
    return jsonify(task)


@app.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id: str):
    if task_id not in TASKS:
        return jsonify({"error": "Task not found"}), 404
    del TASKS[task_id]
    logger.info("DELETE /tasks/%s – deleted", task_id)
    return jsonify({"message": "Task deleted"}), 200


# ── Feature 2 – Search ─────────────────────────────────────────────────────────

@app.route("/tasks/search", methods=["GET"])
def search_tasks():
    query = _sanitize(request.args.get("q", ""))
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    results = [
        t for t in TASKS.values()
        if query.lower() in t["title"].lower() or query.lower() in t["description"].lower()
    ]
    logger.info("GET /tasks/search?q=%s – %d results", query, len(results))
    return jsonify({"results": results, "count": len(results)})


# ── Feature 3 – Health check / metrics ────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("APP_ENV", "development"),
        "task_count": len(TASKS),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("APP_ENV", "development") == "development"
    logger.info("Starting SecureTaskAPI on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
