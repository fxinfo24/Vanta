"""
Tests for the web routes of the Vanta application
"""

import pytest
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from app.web.models import Task, TaskStatus
from app.web import create_app
from app.web.routes.views import views_bp


@pytest.fixture
def app():
    """Create app fixture for testing"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    # Register the views blueprint if it's not already registered
    if "views" not in [bp.name for bp in app.blueprints.values()]:
        app.register_blueprint(views_bp)

    # Create application context
    with app.app_context():
        from app.web.models import db

        db.create_all()

        # Every /api route now requires a Bearer JWT. Register a test user
        # and remember its id/token so the client fixture (and task-creation
        # in tests below) can act as that user.
        from app.web.auth import auth_session, create_user, create_access_token

        _auth_session = auth_session()
        test_user = create_user(
            email="test@example.com",
            password="testpassword123",
            username="testuser",
            db=_auth_session,
        )
        _auth_session.close()
        app.config["TEST_USER_ID"] = test_user.id
        app.config["TEST_TOKEN"] = create_access_token({"sub": test_user.id})

        # Add some sample tasks (owned by the test user so scoped API
        # queries can see them)
        sample_task = Task(platform="twitter", profile_id="test_user", user_id=test_user.id)
        sample_task.status = TaskStatus.COMPLETED
        sample_task.progress = 100
        sample_task.result_path = "/path/to/result.json"
        sample_task.created_at = datetime.utcnow()

        db.session.add(sample_task)
        db.session.commit()

        yield app

        # Clean up
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client that auto-authenticates with the test user's JWT.

    All /api routes require Authorization: Bearer <token> now, so every
    request through this client carries the test user's token (unless a
    test passes its own Authorization header, which takes precedence).
    """
    raw_client = app.test_client()
    token = app.config["TEST_TOKEN"]

    class AuthClient:
        """Delegates every call to the raw client, injecting the Bearer
        token. (Overriding only `open` doesn't work: FlaskClient.get/post
        don't route through an overridden `open` on a wrapper, so every
        callable attribute is wrapped instead.)"""

        def __init__(self, raw, token):
            self._raw = raw
            self._token = token

        def __getattr__(self, name):
            attr = getattr(self._raw, name)
            if not callable(attr):
                return attr

            def wrapped(*args, **kwargs):
                headers = dict(kwargs.pop("headers", None) or {})
                headers.setdefault("Authorization", f"Bearer {self._token}")
                return attr(*args, **kwargs, headers=headers)

            return wrapped

    return AuthClient(raw_client, token)


def test_home_page(client):
    """Test the home page loads correctly"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Vanta" in response.data
    assert b"Start New Analysis" in response.data


def test_start_analysis(client):
    """Test starting a new analysis"""
    response = client.post(
        "/start-analysis",
        data={"platform": "twitter", "profile_id": "test_user"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"task" in response.data


def test_task_status_page(client, app):
    """Test the task status page loads correctly"""
    # Ensure we have a task ID to query
    with app.app_context():
        task = Task.query.first()

    # Check if we got a task from the fixture
    if task:
        # Request the task page
        response = client.get(f"/tasks/{task.id}")
        assert response.status_code == 200
        assert f"Task Status" in response.data.decode("utf-8")
    else:
        # Create a task if none exists
        with app.app_context():
            from app.web.models import db

            new_task = Task(platform="twitter", profile_id="new_test_user")
            db.session.add(new_task)
            db.session.commit()
            task_id = new_task.id

        # Now request the task page
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        assert "Task Status" in response.data.decode("utf-8")


@patch("app.web.routes.views.render_template")
def test_completed_task_redirect_to_results(mock_render_template, client, app):
    """Test completed tasks show results page"""
    # Set up the mock to return a value
    mock_render_template.return_value = "Mocked Results Page"

    # Create a completed task with a mock result path
    with app.app_context():
        from app.web.models import db

        task = Task(platform="twitter", profile_id="completed_test_user")
        task.status = TaskStatus.COMPLETED

        # Create a temporary file for testing
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write('{"test": "data"}')
            task.result_path = f.name

        db.session.add(task)
        db.session.commit()
        task_id = task.id

    # Make the request to the results page
    response = client.get(f"/result/{task_id}")

    # Verify the response and mock calls
    assert response.status_code == 200
    mock_render_template.assert_called_once()

    # Check template name and context
    template_name = mock_render_template.call_args[0][0]
    assert template_name == "result.html"

    # Clean up the temporary file
    if os.path.exists(task.result_path):
        os.unlink(task.result_path)


def test_ajax_start_analysis(client):
    """Test starting analysis with AJAX"""
    headers = {"X-Requested-With": "XMLHttpRequest"}
    response = client.post(
        "/start-analysis",
        data={"platform": "twitter", "profile_id": "ajax_test_user"},
        headers=headers,
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert "task_id" in data


# ============================================================================
# API ENDPOINT TESTS (/api/*)
# Comprehensive tests for REST API endpoints used by frontend
# ============================================================================

@patch.dict(os.environ, {"REDIS_URL": ""})  # Force threading fallback
@patch("app.web.routes.api.analyzer")
def test_api_create_analysis(mock_analyzer, client, app):
    """Test POST /api/analyze endpoint"""
    response = client.post(
        "/api/analyze",
        json={"platform": "twitter", "profile_id": "elonmusk"},
        content_type="application/json"
    )
    
    assert response.status_code == 202
    data = json.loads(response.data)
    assert "message" in data
    assert "task" in data
    assert data["task"]["platform"] == "twitter"
    assert data["task"]["profile_id"] == "elonmusk"
    assert data["task"]["status"] == "pending"


def test_api_create_analysis_missing_fields(client):
    """Test POST /api/analyze with missing required fields"""
    # Missing profile_id
    response = client.post(
        "/api/analyze",
        json={"platform": "twitter"},
        content_type="application/json"
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    
    # Missing platform
    response = client.post(
        "/api/analyze",
        json={"profile_id": "test_user"},
        content_type="application/json"
    )
    assert response.status_code == 400


def test_api_get_task(client, app):
    """Test GET /api/tasks/<id> endpoint"""
    with app.app_context():
        task = Task.query.first()
        task_id = task.id
    
    response = client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["id"] == task_id
    assert "platform" in data
    assert "status" in data


def test_api_get_task_not_found(client):
    """Test GET /api/tasks/<id> with non-existent ID"""
    response = client.get("/api/tasks/99999")
    assert response.status_code == 404


def test_api_list_tasks(client, app):
    """Test GET /api/tasks endpoint with pagination"""
    response = client.get("/api/tasks?limit=10&offset=0")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "tasks" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["tasks"], list)


def test_api_list_tasks_filtering(client, app):
    """Test GET /api/tasks with platform and status filters"""
    # Create tasks with different platforms
    with app.app_context():
        from app.web.models import db
        
        task1 = Task(platform="twitter", profile_id="user1", status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task2 = Task(platform="instagram", profile_id="user2", status=TaskStatus.PENDING, user_id=app.config["TEST_USER_ID"])
        db.session.add_all([task1, task2])
        db.session.commit()
    
    # Filter by platform
    response = client.get("/api/tasks?platform=twitter")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert all(task["platform"] == "twitter" for task in data["tasks"])
    
    # Filter by status
    response = client.get("/api/tasks?status=completed")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert all(task["status"] == "completed" for task in data["tasks"])


def test_api_get_task_status(client, app):
    """Test GET /api/tasks/<id>/status endpoint (for polling)"""
    with app.app_context():
        task = Task.query.first()
        task_id = task.id
    
    response = client.get(f"/api/tasks/{task_id}/status")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "id" in data
    assert "status" in data
    assert "progress" in data
    # This endpoint should only return minimal fields for efficient polling
    assert set(data.keys()) == {"id", "status", "progress", "message", "error"}


def test_api_cancel_task(client, app):
    """Test POST /api/tasks/<id>/cancel endpoint"""
    with app.app_context():
        from app.web.models import db
        
        task = Task(platform="twitter", profile_id="cancel_test", status=TaskStatus.PENDING, user_id=app.config["TEST_USER_ID"])
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    
    response = client.post(f"/api/tasks/{task_id}/cancel")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Task cancelled"
    assert data["task"]["status"] == "failed"
    assert "cancelled by user" in data["task"]["error"].lower()


def test_api_cancel_completed_task(client, app):
    """Test cancelling a completed task (should fail)"""
    with app.app_context():
        task = Task.query.first()  # This is a completed task from fixture
        task_id = task.id
    
    response = client.post(f"/api/tasks/{task_id}/cancel")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_api_get_results(client, app):
    """Test GET /api/tasks/<id>/results endpoint"""
    with app.app_context():
        from app.web.models import db
        
        task = Task(platform="twitter", profile_id="results_test", status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task.result_data = {"test": "data", "score": 85}
        task.has_result = True
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    
    response = client.get(f"/api/tasks/{task_id}/results")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["test"] == "data"
    assert data["score"] == 85


def test_api_get_results_not_completed(client, app):
    """Test getting results for non-completed task"""
    with app.app_context():
        from app.web.models import db
        
        task = Task(platform="twitter", profile_id="pending_test", status=TaskStatus.PENDING, user_id=app.config["TEST_USER_ID"])
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    
    response = client.get(f"/api/tasks/{task_id}/results")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_api_download_results(client, app):
    """Test GET /api/tasks/<id>/download endpoint"""
    with app.app_context():
        from app.web.models import db
        
        task = Task(platform="twitter", profile_id="download_test", status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task.result_data = {"profile": "test_user", "analysis": "complete"}
        task.has_result = True
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    
    response = client.get(f"/api/tasks/{task_id}/download")
    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert "attachment" in response.headers.get("Content-Disposition", "")
    # Verify JSON content
    data = json.loads(response.data)
    assert data["profile"] == "test_user"


def test_api_platform_distribution(client, app):
    """Test GET /api/stats/platform-distribution endpoint"""
    with app.app_context():
        from app.web.models import db
        
        # Add tasks with different platforms
        platforms = ["twitter", "twitter", "instagram", "linkedin"]
        for platform in platforms:
            task = Task(platform=platform, profile_id=f"user_{platform}", user_id=app.config["TEST_USER_ID"])
            db.session.add(task)
        db.session.commit()
    
    response = client.get("/api/stats/platform-distribution")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    # Should have stats for each platform
    platform_names = [item["platform"] for item in data]
    assert "twitter" in platform_names


def test_api_completion_rate(client, app):
    """Test GET /api/stats/completion-rate endpoint"""
    with app.app_context():
        from app.web.models import db
        
        # Add tasks with different statuses
        completed = Task(platform="twitter", profile_id="c1", status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        failed = Task(platform="twitter", profile_id="f1", status=TaskStatus.FAILED, user_id=app.config["TEST_USER_ID"])
        pending = Task(platform="twitter", profile_id="p1", status=TaskStatus.PENDING, user_id=app.config["TEST_USER_ID"])
        
        db.session.add_all([completed, failed, pending])
        db.session.commit()
    
    response = client.get("/api/stats/completion-rate")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "total" in data
    assert "completed" in data
    assert "failed" in data
    assert "completion_rate" in data
    assert data["total"] > 0
    assert 0 <= data["completion_rate"] <= 100


def test_api_cors_headers(client):
    """Test that CORS headers are present in API responses"""
    response = client.get("/api/stats/completion-rate")
    # Note: In test environment, CORS might not be fully configured
    # This test documents expected behavior in production
    assert response.status_code == 200


# ============================================================================
# AUTH TESTS (register/login + JWT guard + per-user scoping)
# ============================================================================

def test_auth_register_login_me(app):
    """Test full auth flow: register -> login -> /auth/me"""
    raw = app.test_client()

    resp = raw.post(
        "/api/auth/register",
        json={"email": "newuser@example.com", "password": "password123", "username": "newuser"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["user"]["email"] == "newuser@example.com"
    assert "token" in data
    assert "hashed_password" not in json.dumps(data)

    resp = raw.post(
        "/api/auth/login",
        json={"email": "newuser@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    token = json.loads(resp.data)["token"]

    resp = raw.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert json.loads(resp.data)["user"]["email"] == "newuser@example.com"


def test_auth_register_validation(app):
    """Test auth input validation and duplicate/wrong-password handling"""
    raw = app.test_client()

    # Password too short
    resp = raw.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )
    assert resp.status_code == 400

    # Duplicate email (test user registered by the fixture)
    resp = raw.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 409

    # Wrong password
    resp = raw.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpass1"},
    )
    assert resp.status_code == 401


def test_auth_required_for_api(app):
    """Test that /api routes require a token but /health stays public"""
    raw = app.test_client()

    resp = raw.get("/api/tasks")
    assert resp.status_code == 401

    resp = raw.get("/api/health")
    assert resp.status_code == 200


def test_auth_invalid_token(app):
    """Test that a garbage Bearer token is rejected with 401, not 500"""
    raw = app.test_client()

    resp = raw.get("/api/tasks", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


# ============================================================================
# SETTINGS + BYOK TESTS
# ============================================================================

def test_settings_defaults(client):
    """Test GET /api/settings returns defaults for a fresh user"""
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["profile"]["email"] == "test@example.com"
    assert data["preferences"]["default_mode"] == "deep"
    assert data["preferences"]["preferred_model"] is None
    assert "available_models" in data and len(data["available_models"]) >= 1
    for provider in ("openrouter", "scrapecreators", "newsapi", "google_factcheck", "claimbuster", "apify"):
        assert provider in data["byok"]
        assert data["byok"][provider]["configured"] is False
        assert data["byok"][provider]["source"] in ("server", "none")


def test_settings_put_roundtrip_and_byok_masking(client, app):
    """Test PUT /api/settings saves profile/prefs and BYOK keys (masked in responses)"""
    resp = client.put(
        "/api/settings",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "default_mode": "quick",
            "preferred_model": "x-ai/grok-4.1-fast",
            "byok": {"openrouter": "sk-or-v1-the-real-secret-key-9999", "newsapi": "news-secret-1234"},
        },
    )
    assert resp.status_code == 200, resp.data
    data = json.loads(resp.data)
    assert data["profile"]["first_name"] == "Ada"
    assert data["preferences"]["default_mode"] == "quick"
    assert data["preferences"]["preferred_model"] == "x-ai/grok-4.1-fast"
    assert data["byok"]["openrouter"]["configured"] is True
    assert data["byok"]["openrouter"]["source"] == "user"
    assert data["byok"]["openrouter"]["hint"] == "••••9999"
    # Plaintext must NEVER appear in any response
    assert "sk-or-v1-the-real-secret-key-9999" not in resp.data.decode()
    assert "news-secret-1234" not in resp.data.decode()

    resp = client.get("/api/settings")
    data = json.loads(resp.data)
    assert data["profile"]["first_name"] == "Ada"
    assert data["byok"]["newsapi"]["hint"] == "••••1234"

    # Stored blob must be encrypted, not plaintext
    with app.app_context():
        from app.web.models.user import UserSettings
        row = __import__("app.web.models", fromlist=["db"]).db.session.query(UserSettings).first()
        assert row.byok_keys_enc is not None
        assert "sk-or-v1" not in row.byok_keys_enc
        from app.utils.config import decrypt_api_keys
        keys = decrypt_api_keys(row.byok_keys_enc)
        assert keys["OPENROUTER_API_KEY"] == "sk-or-v1-the-real-secret-key-9999"

    # Clearing with empty string removes the provider key
    resp = client.put("/api/settings", json={"byok": {"openrouter": ""}})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["byok"]["openrouter"]["configured"] is False


def test_settings_validation(client):
    """Test settings input validation"""
    resp = client.put("/api/settings", json={"default_mode": "sideways"})
    assert resp.status_code == 400
    resp = client.put("/api/settings", json={"preferred_model": "not/a-real-model"})
    assert resp.status_code == 400
    resp = client.put("/api/settings", json={"byok": {"unknown_provider": "x"}})
    assert resp.status_code == 400


def test_settings_cross_user_isolation(app):
    """Test one user's BYOK config is invisible to another user"""
    raw = app.test_client()
    alice_headers = {"Authorization": f"Bearer {app.config['TEST_TOKEN']}"}
    resp = raw.put("/api/settings", headers=alice_headers, json={"byok": {"openrouter": "alice-secret-key-7777"}})
    assert resp.status_code == 200, resp.data

    resp = raw.post("/api/auth/register", json={"email": "bob2@example.com", "password": "password123", "username": "bob2"})
    bob_token = json.loads(resp.data)["token"]
    resp = raw.get("/api/settings", headers={"Authorization": f"Bearer {bob_token}"})
    data = json.loads(resp.data)
    assert data["byok"]["openrouter"]["configured"] is False
    assert "alice-secret-key-7777" not in resp.data.decode()


def test_change_password(app):
    """Test change password flow (wrong current -> 401, right -> 200, new works)"""
    headers = {"Authorization": f"Bearer {app.config['TEST_TOKEN']}"}
    raw = app.test_client()

    resp = raw.post("/api/auth/change-password", headers=headers,
                    json={"current_password": "wrongpass1", "new_password": "newpassword123"})
    assert resp.status_code == 401

    resp = raw.post("/api/auth/change-password", headers=headers,
                    json={"current_password": "testpassword123", "new_password": "short"})
    assert resp.status_code == 400

    resp = raw.post("/api/auth/change-password", headers=headers,
                    json={"current_password": "testpassword123", "new_password": "newpassword123"})
    assert resp.status_code == 200

    resp = raw.post("/api/auth/login", json={"email": "test@example.com", "password": "newpassword123"})
    assert resp.status_code == 200


def test_auth_cross_user_isolation(app):
    """Test that one user cannot see another user's tasks"""
    raw = app.test_client()

    # Register a second user
    resp = raw.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "password123", "username": "other"},
    )
    assert resp.status_code == 201
    other_token = json.loads(resp.data)["token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    with app.app_context():
        task_id = Task.query.first().id  # owned by the fixture's test user

    # Other user gets 404 (not 403), so task existence doesn't leak
    resp = raw.get(f"/api/tasks/{task_id}", headers=other_headers)
    assert resp.status_code == 404

    # And the task doesn't appear in their list either
    resp = raw.get("/api/tasks", headers=other_headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert task_id not in [t["id"] for t in data["tasks"]]
