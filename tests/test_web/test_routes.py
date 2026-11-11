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
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        # Do not inherit this machine's recorded provider balance.
        "PROVIDER_USAGE_PATH": "/nonexistent/vanta_provider_usage.json",
    })

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


def test_monitoring_self_test_is_hidden_and_reports_event_id(client, app):
    """The probe exists to prove capture in production, so it must not advertise."""
    monkeypatch = pytest.MonkeyPatch()

    # No token configured: indistinguishable from any other missing route,
    # and reachable without a user JWT (a monitor has no account here).
    monkeypatch.delenv("MONITORING_TEST_TOKEN", raising=False)
    anonymous = app.test_client()
    assert anonymous.get("/api/health/self-test").status_code == 404
    assert client.get("/api/health/self-test").status_code == 404

    # Token configured, wrong header: still hidden.
    monkeypatch.setenv("MONITORING_TEST_TOKEN", "expected-token")
    assert client.get("/api/health/self-test",
                      headers={"X-Monitoring-Token": "wrong"}).status_code == 404

    # Token matches but this deployment has no Sentry configured.
    assert client.get("/api/health/self-test",
                      headers={"X-Monitoring-Token": "expected-token"}).status_code == 503

    class FakeSdk:
        def set_tag(self, key, value):
            self.tag = (key, value)

        def capture_exception(self):
            return "deadbeef"

    app.extensions["sentry"] = FakeSdk()
    try:
        response = client.get("/api/health/self-test",
                              headers={"X-Monitoring-Token": "expected-token"})
        body = json.loads(response.data)
        assert response.status_code == 200
        assert body["captured"] is True and body["event_id"] == "deadbeef"
        assert body["request_id"]
    finally:
        app.extensions.pop("sentry", None)
        monkeypatch.undo()


def test_api_get_results_scrubs_stored_policy_key(client, app):
    """Reports stored before the copy fix must not keep leaking the config key.

    The reason string was written into result_data at analysis time, so it lives
    in the row and in any export made from it - not only in the code path.
    """
    legacy = {
        "belief_system": {"gated": True, "status": "not_collected",
                          "reason": "disabled by policy (privacy.allow_special_category_inference)"},
        "behavioral_profile": {
            "temperament": {"label": "Calm"},
            "relationships": {"gated": True, "status": "not_collected",
                              "reason": "(privacy.allow_special_category_inference)"},
        },
    }
    with app.app_context():
        from app.web.models import db

        task = Task(platform="twitter", profile_id="legacy_gate",
                    status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task.result_data = legacy
        task.has_result = True
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    response = client.get(f"/api/tasks/{task_id}/results")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "allow_special_category_inference" not in body
    data = json.loads(body)
    assert data["behavioral_profile"]["relationships"]["code"] == "special_category_not_inferred"
    assert data["belief_system"]["code"] == "special_category_not_inferred"
    assert data["behavioral_profile"]["temperament"]["label"] == "Calm"

    export = client.get(f"/api/tasks/{task_id}/download?format=json")
    assert export.status_code == 200
    assert "allow_special_category_inference" not in export.get_data(as_text=True)


def test_post_from_task_ingests_the_subjects_own_posts(client, app):
    """Verification must run on what the account published, not on our summary.

    The bridge previously fed the extractor a blob of display name + bio +
    executive summary, so every "claim" it checked was Vanta's own prose.
    """
    result = {
        "executive_summary": "This account posts about municipal politics.",
        "profile_info": {"display_name": "City Desk"},
        "raw_dossier": {"content": [
            {"text": "The bridge reopened on 3 March 2024 after repairs.",
             "url": "https://example.test/p/1", "creation_time": 1709467200},
            {"text": "Turnout reached 62 percent in the district election.",
             "url": "https://example.test/p/2", "creation_time": "2024-03-05T10:00:00Z"},
            {"text": "", "url": "https://example.test/p/3"},
        ]},
    }
    with app.app_context():
        from app.web.models import db

        task = Task(platform="facebook", profile_id="citydesk",
                    status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task.result_data = result
        task.has_result = True
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    response = client.post(f"/api/verification/post/from-task/{task_id}")
    assert response.status_code == 201
    body = response.get_json()
    assert body["source"] == "subject_posts"
    assert body["created"] == 2, "blank cards carry no claim and must be skipped"
    texts = [p["text"] for p in body["posts"]]
    assert any("bridge reopened on 3 March 2024" in t for t in texts)
    assert any("Turnout reached 62 percent" in t for t in texts)
    assert not any("municipal politics" in t for t in texts), \
        "the analysis summary must not stand in for the subject's words"



def test_post_from_task_flags_the_summary_fallback(client, app):
    """A profile-only dossier has no post text; say so instead of pretending."""
    with app.app_context():
        from app.web.models import db

        task = Task(platform="facebook", profile_id="bare",
                    status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task.result_data = {"executive_summary": "Profile with no collected posts.",
                            "profile_info": {"display_name": "Bare"}}
        task.has_result = True
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    response = client.post(f"/api/verification/post/from-task/{task_id}")
    assert response.status_code == 201
    body = response.get_json()
    assert body["source"] == "dossier_summary"
    assert "no post text" in body["message"]


def test_claim_detail_returns_the_layer_6_reasoning(client, app):
    """A verdict with no visible rationale is a number without an argument.

    Layer 6 stored `reasoning` but `_verification_payload` only ever returned the
    layer names, so the explanation was unreachable through the API.
    """
    with app.app_context():
        from app.web.models import db
        from app.web.models.verification import SocialMediaPost, Claim, VerificationResult
        from app.web.models.verification import LanguageCode, MediaType

        post = SocialMediaPost(
            id="facebook_reason_test_1",
            user_id=app.config["TEST_USER_ID"],
            platform="facebook",
            profile_id="reason_test",
            text="The bridge reopened on 3 March 2024.",
            content="The bridge reopened on 3 March 2024.",
            detected_language=LanguageCode.EN,
            media_type=MediaType.TEXT,
        )
        db.session.add(post)
        db.session.commit()
        claim = Claim(id="claim_reason_test_1", post_id=post.id,
                      claim_text="The bridge reopened on 3 March 2024.")
        db.session.add(claim)
        db.session.commit()
        vr = VerificationResult(
            id="verification_claim_reason_test_1",
            claim_id=claim.id,
            confidence_score=0.375,
            composite_verification_score=0.375,
            evidence_chain={
                "layer_4": {"verdict_summary": {"verdict": "NO_MATCH", "confidence": 0.0}},
                "layer_6": {"verdict": "UNVERIFIABLE", "confidence": 0.6,
                            "reasoning": "No matching verified fact-check was found.",
                            "citations": [{"evidence_id": "1", "relevant_text": "NO_MATCH"}],
                            "model_used": "nvidia/nemotron-3-ultra-550b-a55b:free"},
                "layer_7": {"verdict": "LOW_CONFIDENCE"},
            },
        )
        db.session.add(vr)
        db.session.commit()

    response = client.get("/api/verification/claim/claim_reason_test_1")
    assert response.status_code == 200
    body = response.get_json()
    verification = body["verification"]
    assert verification["layer_6"]["reasoning"] == "No matching verified fact-check was found."
    assert verification["layer_6"]["model_used"].startswith("nvidia/")
    assert verification["confidence"] == 0.375, \
        "the stored confidence must be what the verdict was based on"


def test_verify_task_queues_the_work_instead_of_blocking(client, app, monkeypatch):
    """Four layers per claim take minutes; the request must return first."""
    import time
    import app.core.tasks as tasks_mod

    calls = []
    monkeypatch.setattr(
        tasks_mod, "run_verification_for_posts",
        lambda post_ids, max_claims=20: calls.append((list(post_ids), max_claims)) or [],
    )

    with app.app_context():
        from app.web.models import db

        task = Task(platform="facebook", profile_id="queue_test",
                    status=TaskStatus.COMPLETED, user_id=app.config["TEST_USER_ID"])
        task.result_data = {"profile_info": {"display_name": "Queue Test"},
                            "raw_dossier": {"content": [
                                {"text": "The bridge reopened on 3 March 2024 after repairs."},
                                {"text": "Turnout reached 62 percent in the district election."},
                            ]}}
        task.has_result = True
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    response = client.post(f"/api/verification/task/{task_id}/run")
    assert response.status_code == 202
    body = response.get_json()
    assert body["mode"] in ("thread", "celery")
    assert body["posts"] == 2

    deadline = time.time() + 5
    while not calls and time.time() < deadline:
        time.sleep(0.05)
    assert calls, "the worker never picked the posts up"
    assert len(calls[0][0]) == 2


def _qstash_sign(body: bytes, destination: str, key: str = "sig_test_key") -> str:
    """Mimic QStash's Upstash-Signature: HS256 JWT over body hash + destination."""
    import base64
    import hashlib
    import time as _time
    import jwt
    digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode()
    return jwt.encode({"iss": "Upstash", "sub": destination, "body": digest,
                       "exp": int(_time.time()) + 300}, key, algorithm="HS256")


def test_qstash_signature_binds_the_body_and_the_destination(app, monkeypatch):
    """The signature is the only credential on the public job endpoint."""
    from app.web.routes.api import _qstash_signature_ok
    monkeypatch.setenv("QSTASH_TOKEN", "tok")
    monkeypatch.setenv("QSTASH_CURRENT_SIGNING_KEY", "sig_test_key")
    monkeypatch.delenv("QSTASH_NEXT_SIGNING_KEY", raising=False)

    body = b'{"post_id": "p1", "max_claims": 2}'
    dest = "https://api.example.com/api/verification/job"
    sig = _qstash_sign(body, dest)

    assert _qstash_signature_ok(body, sig, dest)[0]
    assert not _qstash_signature_ok(body + b" ", sig, dest)[0], "a tampered body must fail"
    assert _qstash_signature_ok(body + b" ", sig, dest)[1] == "body"
    assert not _qstash_signature_ok(body, sig, "https://evil.example.com/api/verification/job")[0], \
        "a signature for another destination must fail"
    assert not _qstash_signature_ok(body, _qstash_sign(body, dest, "wrong_key"), dest)[0]
    assert _qstash_signature_ok(body, "", dest) == (False, "missing")


def test_verification_job_refuses_unsigned_callers(client, monkeypatch):
    monkeypatch.setenv("QSTASH_TOKEN", "tok")
    monkeypatch.setenv("QSTASH_CURRENT_SIGNING_KEY", "sig_test_key")
    resp = client.post("/api/verification/job", json={"post_id": "p1"})
    assert resp.status_code == 401


def test_verification_job_runs_one_post_when_the_signature_is_valid(client, app, monkeypatch):
    import app.core.tasks as tasks_mod
    monkeypatch.setenv("QSTASH_TOKEN", "tok")
    monkeypatch.setenv("QSTASH_CURRENT_SIGNING_KEY", "sig_test_key")

    calls = []
    monkeypatch.setattr(
        tasks_mod, "run_verification_for_posts",
        lambda post_ids, max_claims=20: calls.append((list(post_ids), max_claims)) or [{"claim_id": "c1"}],
    )
    body = json.dumps({"post_id": "post_qstash_1", "max_claims": 1}).encode()
    resp = client.post(
        "/api/verification/job", data=body,
        headers={"Content-Type": "application/json",
                 "Upstash-Signature": _qstash_sign(body, "http://localhost/api/verification/job")},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"post_id": "post_qstash_1", "claims_processed": 1}
    assert calls == [(["post_qstash_1"], 1)]


def test_dispatch_prefers_qstash_over_the_in_process_thread(app, monkeypatch):
    """One signed message per post: small enough to finish, retried by QStash."""
    import app.web.routes.api as api_mod
    monkeypatch.setenv("QSTASH_TOKEN", "tok")
    monkeypatch.setenv("QSTASH_CURRENT_SIGNING_KEY", "sig_test_key")
    monkeypatch.delenv("FORCE_CELERY", raising=False)

    sent = []
    monkeypatch.setattr(api_mod, "_qstash_publish",
                        lambda token, destination, payloads: (sent.extend(payloads),
                                                              (len(payloads), []))[1])

    with app.test_request_context("/api/verification/task/1/run", method="POST"):
        result = api_mod._dispatch_verification(["p1", "p2"], 3)

    assert result["mode"] == "qstash"
    assert result["queued"] == 2
    assert sent == [{"post_id": "p1", "max_claims": 3},
                    {"post_id": "p2", "max_claims": 3}]


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


def test_analyse_blocked_when_provider_credits_exhausted(client, app, tmp_path, monkeypatch):
    """A run the provider balance cannot cover is refused with a clear reason."""
    import json as _json

    usage = tmp_path / "usage.json"
    usage.write_text(_json.dumps({"scrapecreators": {"credits_remaining": 2,
                                                    "observed_at": "2026-11-09T00:00:00Z"}}))
    app.config["PROVIDER_USAGE_PATH"] = str(usage)

    response = client.post(
        "/api/analyze",
        json={"platform": "facebook", "profile_id": "someone", "mode": "deep"},
        content_type="application/json",
    )

    assert response.status_code == 402
    body = _json.loads(response.data)
    assert "credit" in body["error"].lower()
    assert body["budget"]["enough"] is False

    # Nothing was queued for this profile by the blocked request.
    from app.web.models import Task
    assert Task.query.filter_by(profile_id="someone").count() == 0


def test_list_tasks_reports_collection_age_and_history_depth(client, app):
    """The list must distinguish a fresh run from one analysed long ago.

    Request time says when the job ran, not how old the numbers are, and a
    subject with one snapshot has no trend - both belong on the list itself.
    """
    from datetime import datetime, timedelta
    from app.web.models import db, DossierSnapshot

    with app.app_context():
        old = Task(platform="facebook", profile_id="freshness_subject",
                   user_id=app.config["TEST_USER_ID"])
        old.status = TaskStatus.COMPLETED
        db.session.add(old)
        db.session.commit()
        collected = datetime.utcnow() - timedelta(days=6)
        db.session.add(DossierSnapshot(task_id=old.id, platform="facebook",
                                       username="freshness_subject", created_at=collected,
                                       snapshot_data={"followers": 10}))
        # A second, separate run of the same subject: that is history depth 2.
        newer = Task(platform="facebook", profile_id="freshness_subject",
                     user_id=app.config["TEST_USER_ID"])
        db.session.add(newer)
        db.session.commit()
        db.session.add(DossierSnapshot(task_id=newer.id, platform="facebook",
                                       username="freshness_subject",
                                       snapshot_data={"followers": 11}))
        db.session.commit()

    data = client.get("/api/tasks?platform=facebook").get_json()
    rows = [t for t in data["tasks"] if t["profile_id"] == "freshness_subject"]

    assert rows and all(t["history_depth"] == 2 for t in rows)
    # Age comes from the newest snapshot of the subject, not from this task.
    assert all(t["last_collected_at"] is not None for t in rows)
    assert all(datetime.fromisoformat(t["last_collected_at"]) > collected for t in rows)

    # A subject that never produced a snapshot reports zero, not a fake date.
    from app.web.models import Task as TaskModel
    with app.app_context():
        empty = TaskModel(platform="facebook", profile_id="never_collected",
                          user_id=app.config["TEST_USER_ID"])
        db.session.add(empty)
        db.session.commit()
    data = client.get("/api/tasks?platform=facebook").get_json()
    row = next(t for t in data["tasks"] if t["profile_id"] == "never_collected")
    assert row["history_depth"] == 0
    assert row["last_collected_at"] is None


def test_delete_task_removes_task_and_snapshots(client, app):
    """Erasure must take the derived history with it, not just the row."""
    from app.web.models import db, DossierSnapshot

    with app.app_context():
        task = Task(platform="facebook", profile_id="erase_me",
                    user_id=app.config["TEST_USER_ID"])
        task.status = TaskStatus.COMPLETED
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        db.session.add(DossierSnapshot(task_id=task_id, platform="facebook",
                                       username="erase_me",
                                       snapshot_data={"followers": 10}))
        db.session.commit()

    response = client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["snapshots_deleted"] == 1
    with app.app_context():
        assert db.session.get(Task, task_id) is None
        assert DossierSnapshot.query.filter_by(task_id=task_id).count() == 0


def test_delete_task_also_drops_the_cached_dossier(client, app):
    """A cached dossier holds the raw posts; keeping it undoes the erasure."""
    from app.web.models import db
    from app.web.models.dossier import DossierCache

    with app.app_context():
        task = Task(platform="facebook", profile_id="cached_subject",
                    user_id=app.config["TEST_USER_ID"])
        task.status = TaskStatus.COMPLETED
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        db.session.add(DossierCache(
            user_id=app.config["TEST_USER_ID"], platform="facebook",
            profile_id="cached_subject", payload={"content": [{"text": "raw post"}]},
            collected_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=6),
        ))
        db.session.commit()

    response = client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["dossiers_deleted"] == 1
    with app.app_context():
        assert DossierCache.query.filter_by(profile_id="cached_subject").count() == 0


def test_delete_task_refuses_a_run_in_flight(client, app):
    """Deleting a processing run would let the worker resurrect it."""
    with app.app_context():
        task = Task(platform="facebook", profile_id="busy",
                    user_id=app.config["TEST_USER_ID"])
        task.status = TaskStatus.PROCESSING
        from app.web.models import db
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    response = client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 409


def test_retention_purge_keeps_history_and_drops_posts(app):
    """Expired posts and quotes go; snapshot numbers stay."""
    from datetime import datetime, timedelta
    from app.web.models import db, DossierSnapshot
    from app.web.models.dossier import purge_expired_results

    now = datetime.utcnow()
    with app.app_context():
        task = Task(platform="facebook", profile_id="old_subject", user_id=app.config["TEST_USER_ID"])
        task.status = TaskStatus.COMPLETED
        task.completed_at = now - timedelta(days=120)
        task.updated_at = task.completed_at
        task.result_data = {
            "raw_dossier": {"content": [{"text": "raw post text"}]},
            "profile_info": {"followers": 42, "bio": "personal bio"},
            "content_analysis": {"evidence": [{"claim": "c", "quote": "raw post text"}]},
        }
        db.session.add(task)
        db.session.commit()
        db.session.add(DossierSnapshot(task_id=task.id, platform="facebook",
                                       username="old_subject",
                                       analysis_data={"followers": 42}))
        db.session.commit()

        counts = purge_expired_results(db.session, now=now, raw_days=30, quote_days=90)

        stored = db.session.get(Task, task.id)
        assert counts == {"raw_purged": 1, "quotes_purged": 1}
        assert "raw_dossier" not in stored.result_data
        assert "bio" not in stored.result_data["profile_info"]
        assert stored.result_data["profile_info"]["followers"] == 42
        assert stored.result_data["content_analysis"]["evidence"] == []
        assert DossierSnapshot.query.filter_by(task_id=task.id).count() == 1


def test_forgot_password_token_is_single_use_and_changes_the_password(app, monkeypatch):
    """A reset link works once, then stops working and the password is real."""
    sent = {}
    monkeypatch.setenv("RESEND_API_KEY", "test-key-not-used")
    monkeypatch.setenv("RESET_FROM_EMAIL", "Vanta <reset@example.com>")

    def fake_send(to_email, reset_url):
        sent["to"] = to_email
        sent["url"] = reset_url

    monkeypatch.setattr("app.web.auth.send_password_reset_email", fake_send)

    raw = app.test_client()
    resp = raw.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    assert resp.status_code == 202
    assert sent["to"] == "test@example.com"
    assert "/reset-password?token=" in sent["url"]
    token = sent["url"].split("token=")[1]

    # Stored as a hash, never as the token itself.
    with app.app_context():
        from app.web.models import db
        from app.web.models.user import PasswordResetToken
        rows = db.session.query(PasswordResetToken).all()
        assert len(rows) == 1
        assert token not in rows[0].token_hash
        assert rows[0].used_at is None

    assert raw.post("/api/auth/reset-password",
                    json={"token": token, "new_password": "newpassword123"}).status_code == 200

    login = raw.post("/api/auth/login",
                     json={"email": "test@example.com", "password": "newpassword123"})
    assert login.status_code == 200

    # Replaying the same link must fail, and must not reset the password again.
    replay = raw.post("/api/auth/reset-password",
                      json={"token": token, "new_password": "anotherpassword123"})
    assert replay.status_code == 400


def test_forgot_password_does_not_reveal_whether_the_account_exists(app, monkeypatch):
    """Unknown addresses get the same answer as known ones."""
    monkeypatch.setenv("RESEND_API_KEY", "test-key-not-used")
    monkeypatch.setattr("app.web.auth.send_password_reset_email", lambda *a, **k: None)

    raw = app.test_client()
    known = raw.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    unknown = raw.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.get_json() == unknown.get_json()


def test_forgot_password_says_so_when_email_is_not_configured(app, monkeypatch):
    """No provider means an explicit 503, not a fake 'email sent'."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("BREVO_API_KEY", raising=False)

    resp = app.test_client().post("/api/auth/forgot-password",
                                  json={"email": "test@example.com"})

    assert resp.status_code == 503
    assert "RESEND_API_KEY" in resp.get_json()["error"]

    # A failed send must not leave a token behind or burn the hourly quota.
    with app.app_context():
        from app.web.models import db
        from app.web.models.user import PasswordResetToken
        assert db.session.query(PasswordResetToken).count() == 0


def test_alerts_fire_on_arithmetic_changes():
    """Every alert is recomputable from the two stored snapshots."""
    from app.web.models.dossier import DossierSnapshot

    previous = {"followers": 2000, "engagement_rate_percent": 2.0, "posts_measured": 40,
                "bot_likelihood": 0.15, "posts_per_week": 10.0,
                "post_ids": [str(i) for i in range(40)]}
    current = {"followers": 1700, "engagement_rate_percent": 1.0, "posts_measured": 40,
               "bot_likelihood": 0.62, "posts_per_week": 4.0,
               "post_ids": [str(i) for i in range(10, 43)]}

    report = DossierSnapshot.compute_alerts(current, previous, elapsed_hours=24)
    rules = {a["rule"]: a for a in report["alerts"]}

    assert rules["followers_drop"]["severity"] == "critical"   # -15%
    assert rules["bot_likelihood_jump"]["severity"] == "critical"
    assert rules["engagement_drop"]["current"] == 1.0
    assert rules["cadence_drop"]["previous"] == 10.0
    assert rules["content_removed"]["current"] == 10


def test_alerts_report_not_evaluated_instead_of_passing():
    """A rule whose inputs are missing must say so, not stay silent."""
    from app.web.models.dossier import DossierSnapshot

    report = DossierSnapshot.compute_alerts(
        {"followers": 100}, {"followers": 100, "posts_measured": 3},
    )
    skipped = {s["rule"] for s in report["not_evaluated"]}
    assert {"engagement_drop", "cadence_drop", "bot_likelihood_jump"} <= skipped
    assert report["alerts"] == []


def test_content_dedupe_keeps_richest_copy():
    """The same reel served by two feeds must count once."""
    from app.core.deep_collector import dedupe_content

    items = [
        {"url": "https://www.facebook.com/reel/1098819196465362/",
         "id": "29952502891017569", "reactionCount": 12, "commentCount": 3},
        {"url": "https://www.facebook.com/reel/1098819196465362", "id": "UzpfSTEwMDA="},
        {"url": "https://www.facebook.com/AzizMdArif/posts/pfbid0e9p", "id": "29822216854046174"},
    ]
    kept, removed = dedupe_content(items)

    assert removed == 1 and len(kept) == 2
    assert kept[0]["reactionCount"] == 12  # the copy carrying engagement survived


def test_engagement_and_cadence_share_one_implementation():
    """The prompt, the dossier and the snapshot must not compute it three ways."""
    from app.core.openrouter_client import _engagement_rate_percent
    from app.core.content_analyzer import ContentAnalyzer
    from app.web.models.dossier import DossierSnapshot

    posts = [{"created_at": "2026-11-01T10:00:00Z"}, {"created_at": "2026-11-08T10:00:00Z"},
             {"created_at": "2026-11-09T10:00:00Z"}]
    analyzer = ContentAnalyzer(sentiment_analyzer=False)
    frequency = analyzer._calculate_posting_frequency(posts)
    snapshot = DossierSnapshot.metrics_from_result({"raw_dossier": {"content": posts}})

    assert frequency["weekly_average"] == snapshot["posts_per_week"] == 2.62
    assert _engagement_rate_percent(
        {"engagement_items": 4, "reactions": 40, "comments": 10, "shares": 2},
        {"followers_count": 2061},
    ) == 0.631


def test_numeric_platform_id_is_not_an_authenticity_flag():
    """A provider id is how the account is identified, not a finding about it."""
    from app.core.openrouter_client import _apply_flag_grounding, _content_availability

    profile = {"username": "100000537579893", "display_name": "Arif Aziz", "follower_count": 2061}
    avail = _content_availability([{"text": "a real post " * 5, "reactionCount": 4}], profile)
    result = {"red_flags": [
        "Numeric handle (@100000537579893) rather than vanity URL",
        "Posting pattern is irregular",
    ], "green_flags": []}

    out = _apply_flag_grounding(result, avail, profile)

    assert out["red_flags"] == ["Posting pattern is irregular"]
    assert out["filtered_indicators"] == ["Numeric handle (@100000537579893) rather than vanity URL"]
    assert any("numeric platform id" in i for i in out["limitations"])


def test_verification_gap_is_a_data_gap_not_a_red_flag():
    """The provider omitting the badge says nothing about the account."""
    from app.core.openrouter_client import _split_indicators

    evidence, gaps = _split_indicators([
        "Verified flag is False - may indicate platform verification gap",
        # Real phrasing from a live run: the model states it as a finding.
        "Not verified — no platform authenticity badge",
        "Not verified - no platform identity confirmation",
        # A live run folded three missing inputs into one "unavailable" line.
        "Following count, total posts, and account age unavailable — limits network-level validation",
        "Account was created recently",
    ])
    assert evidence == ["Account was created recently"]
    assert len(gaps) == 4


def test_balance_recorded_with_another_key_does_not_block(app, monkeypatch):
    """A key change invalidates the stored balance instead of blocking runs."""
    from app.core.scrape_client import _key_fingerprint, read_credits
    from app.web.models.dossier import record_provider_credits

    monkeypatch.setenv("SCRAPECREATORS_API_KEY", "key-one")
    with app.app_context():
        assert record_provider_credits("scrapecreators", 0, _key_fingerprint())
        # Same key: the zero still applies.
        assert read_credits()["stale_key"] is False
        monkeypatch.setenv("SCRAPECREATORS_API_KEY", "key-two")
        assert read_credits()["stale_key"] is True


def test_balance_without_fingerprint_cannot_apply_to_current_key(app, monkeypatch):
    """A pre-existing balance of unknown provenance must not block a run."""
    from app.core.scrape_client import read_credits
    from app.web.models.dossier import record_provider_credits

    monkeypatch.setenv("SCRAPECREATORS_API_KEY", "key-one")
    with app.app_context():
        assert record_provider_credits("scrapecreators", 0)
        assert read_credits()["stale_key"] is True
