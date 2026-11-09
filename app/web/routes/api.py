# app/web/routes/api.py
"""
Vanta API Routes
Handles API endpoints for tasks and analysis results
"""
from flask import Blueprint, jsonify, request, current_app, send_file, g
from pathlib import Path
from datetime import datetime
import json
import threading
import re
import os
import logging

from app.core.analyzer import SocialMediaAnalyzer
from ..models import db, Task, TaskStatus
from ..models.user import User, UserSettings
from ..auth import (auth_session, authenticate_user, create_access_token,
                    create_user, get_or_create_settings, load_user_context,
                    user_to_dict, verify_password, hash_password,
                    AuthenticationError)

logger = logging.getLogger("api")

# Initialize analyzer
analyzer = SocialMediaAnalyzer()

api_bp = Blueprint("api", __name__)

# ---------------------------------------------------------------------------
# Authentication + per-user scoping
# ---------------------------------------------------------------------------
# Every /api route requires a Bearer JWT except /health and /auth/*.
# g.current_user is set by the guard; handlers scope all queries to
# g.current_user.id so one user can never see another's analyses.

_PUBLIC_ENDPOINTS = {
    "api.health_check", "api.auth_register", "api.auth_login",
    "api.auth_forgot_password", "api.auth_reset_password",
}


@api_bp.before_request
def _require_auth():
    if request.method == "OPTIONS":
        return None
    if request.endpoint in _PUBLIC_ENDPOINTS:
        return None
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": "Authentication required (Bearer token)"}), 401
    session = auth_session()
    try:
        from ..auth import get_current_user
        g.current_user = get_current_user(header[len("Bearer "):].strip(), session)
    except AuthenticationError as e:
        return jsonify({"error": str(e)}), 401
    finally:
        session.close()
    # Install the user's BYOK keys + preferences so every client used by
    # this (synchronous) request resolves them first. Background threads
    # and Celery set their own context from the task's user_id.
    from app.utils.config import set_user_context
    g._ctx_token = set_user_context(load_user_context(g.current_user.id))
    return None


@api_bp.teardown_request
def _reset_user_context(exc=None):
    """Reset the per-user execution context after each request."""
    token = g.pop("_ctx_token", None)
    if token is not None:
        from app.utils.config import reset_user_context
        reset_user_context(token)


def _uid():
    """Authenticated user's id for query scoping."""
    return g.current_user.id


def _own_task(task_id):
    """Fetch a task only if it belongs to the current user (404 otherwise,
    so task existence doesn't leak across users)."""
    task = Task.query.get(task_id)
    if task is None or task.user_id != _uid():
        return None
    return task


def _own_post(post_id):
    """Fetch a verification post only if it belongs to the current user."""
    from app.web.models.verification import SocialMediaPost
    post = db.session.query(SocialMediaPost).filter_by(id=post_id).first()
    if post is None or post.user_id != _uid():
        return None
    return post


@api_bp.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    session = auth_session()
    try:
        user = create_user(
            email=email, password=password,
            username=str(data.get("username") or "").strip() or None,
            first_name=str(data.get("first_name") or "").strip() or None,
            last_name=str(data.get("last_name") or "").strip() or None,
            db=session,
        )
        token = create_access_token({"sub": user.id})
        return jsonify({"user": user_to_dict(user), "token": token}), 201
    except AuthenticationError as e:
        return jsonify({"error": str(e)}), 409
    finally:
        session.close()


@api_bp.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    session = auth_session()
    try:
        user = authenticate_user(email, password, session)
        if user is None:
            # Generic message: don't reveal whether email or password was wrong
            return jsonify({"error": "Invalid email or password"}), 401
        token = create_access_token({"sub": user.id})
        return jsonify({"user": user_to_dict(user), "token": token}), 200
    finally:
        session.close()


@api_bp.route("/auth/forgot-password", methods=["POST"])
def auth_forgot_password():
    """Email a one-time reset link.

    The response is identical whether or not the address has an account, so this
    endpoint cannot be used to enumerate users. When no email provider is
    configured the API says so (503) instead of reporting a send that never
    happened.
    """
    from ..auth import (EmailNotConfigured, EmailDeliveryError, issue_reset_token,
                        recent_reset_requests, send_password_reset_email)

    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Valid email is required"}), 400

    generic = {"message": "If that address has an account, a reset link has been sent."}
    session = auth_session()
    try:
        user = session.query(User).filter(User.email == email).first()
        if user is None or not user.is_active:
            return jsonify(generic), 202
        if recent_reset_requests(session, user.id) >= 3:
            # Silent no-op: rate limiting must not reveal that the account exists.
            logger.info(f"Reset request throttled for user {user.id}")
            return jsonify(generic), 202

        raw = issue_reset_token(session, user)
        base = (os.getenv("FRONTEND_URL") or request.host_url).rstrip("/")
        reset_url = f"{base}/reset-password?token={raw}"
        try:
            send_password_reset_email(email, reset_url)
        except EmailNotConfigured as e:
            return jsonify({"error": str(e)}), 503
        except EmailDeliveryError as e:
            logger.error(f"Reset email failed for user {user.id}: {e}")
            return jsonify({"error": "The email provider rejected the message. Try again later."}), 502
        logger.info(f"Password reset link issued for user {user.id}")
        return jsonify(generic), 202
    finally:
        session.close()


@api_bp.route("/auth/reset-password", methods=["POST"])
def auth_reset_password():
    """Redeem a one-time token and set a new password."""
    from ..auth import consume_reset_token

    data = request.get_json() or {}
    token = str(data.get("token", "")).strip()
    new = str(data.get("new_password", ""))
    if len(new) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    session = auth_session()
    try:
        user = consume_reset_token(session, token)
        if user is None:
            return jsonify({"error": "This reset link is invalid, expired, or already used"}), 400
        user.hashed_password = hash_password(new)
        session.commit()
        return jsonify({"message": "Password updated. You can sign in now."}), 200
    finally:
        session.close()


@api_bp.route("/auth/me", methods=["GET"])
def auth_me():
    return jsonify({"user": user_to_dict(g.current_user)})


@api_bp.route("/auth/change-password", methods=["POST"])
def auth_change_password():
    data = request.get_json() or {}
    current = str(data.get("current_password") or "")
    new = str(data.get("new_password") or "")
    if len(new) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    session = auth_session()
    try:
        user = session.query(User).filter_by(id=g.current_user.id).first()
        if user is None or not verify_password(current, user.hashed_password):
            return jsonify({"error": "Current password is incorrect"}), 401
        user.hashed_password = hash_password(new)
        session.commit()
        return jsonify({"message": "Password updated"}), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Settings + BYOK (bring your own key)
# ---------------------------------------------------------------------------
# Keys are stored Fernet-encrypted and are NEVER returned in plaintext:
# responses only report per-provider status (configured / source / hint).

# Canonical OpenRouter model catalog (label -> full id). Preferred-model
# validation checks against these ids plus the server-configured model.
def _model_options():
    from app.core.openrouter_client import OpenRouterClient
    catalog = [{"label": k, "id": v} for k, v in OpenRouterClient(None).models.items()]
    from app.utils.config import DEFAULT_OPENROUTER_MODEL
    ids = {m["id"] for m in catalog}
    env_model = os.getenv("OPENROUTER_MODEL")
    extra = {DEFAULT_OPENROUTER_MODEL} | ({env_model} if env_model else set())
    for mid in sorted(extra - ids):
        catalog.append({"label": mid, "id": mid})
    return catalog


def _byok_status(user_keys: dict) -> dict:
    from app.utils.config import BYOK_PROVIDERS, mask_key
    out = {}
    for provider, meta in BYOK_PROVIDERS.items():
        env_var = meta["env_var"]
        key = user_keys.get(env_var)
        out[provider] = {
            "label": meta["label"],
            "configured": bool(key),
            # source is informational only; resolution order is user -> env
            "source": "user" if key else ("server" if os.getenv(env_var) else "none"),
            "hint": mask_key(key),
        }
    return out


def _settings_payload(user, settings, user_keys: dict):
    return {
        "profile": {
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "preferences": {
            "default_mode": settings.default_mode or "deep",
            "preferred_model": settings.preferred_model,
        },
        "available_models": _model_options(),
        "byok": _byok_status(user_keys),
    }


def _settings_row():
    session = auth_session()
    try:
        row = session.query(UserSettings).filter_by(user_id=g.current_user.id).first()
        if row is None:
            row = UserSettings(user_id=g.current_user.id, default_mode="deep")
            session.add(row)
            session.commit()
        # Snapshot plain values while the session is open
        return {
            "default_mode": row.default_mode or "deep",
            "preferred_model": row.preferred_model,
            "byok_keys_enc": row.byok_keys_enc,
        }
    finally:
        session.close()


@api_bp.route("/settings", methods=["GET"])
def get_settings():
    from app.utils.config import decrypt_api_keys
    row = _settings_row()
    user_keys = decrypt_api_keys(row["byok_keys_enc"])
    fake_settings = type("S", (), row)()
    return jsonify(_settings_payload(g.current_user, fake_settings, user_keys))


@api_bp.route("/settings", methods=["PUT"])
def update_settings():
    data = request.get_json() or {}
    from app.utils.config import BYOK_PROVIDERS, encrypt_api_keys, decrypt_api_keys

    session = auth_session()
    try:
        user = session.query(User).filter_by(id=g.current_user.id).first()
        settings = session.query(UserSettings).filter_by(user_id=g.current_user.id).first()
        if settings is None:
            settings = UserSettings(user_id=g.current_user.id, default_mode="deep")
            session.add(settings)

        # --- profile fields (setattr: dict writes bypass SQLAlchemy
        # change-tracking and would silently not persist) ---
        for field in ("first_name", "last_name"):
            if field in data:
                setattr(user, field, str(data[field] or "").strip()[:100] or None)
        if "username" in data:
            username = str(data["username"] or "").strip()
            if username:
                taken = session.query(User).filter(
                    User.username == username, User.id != user.id
                ).first()
                if taken:
                    return jsonify({"error": "Username already taken"}), 409
                user.username = username
            else:
                user.username = None

        # --- preferences ---
        if "default_mode" in data:
            mode = str(data["default_mode"] or "").strip().lower()
            if mode not in ("quick", "deep"):
                return jsonify({"error": "default_mode must be 'quick' or 'deep'"}), 400
            settings.default_mode = mode
        if "preferred_model" in data:
            model = data["preferred_model"]
            if model is None or (isinstance(model, str) and not model.strip()):
                settings.preferred_model = None
            else:
                allowed = {m["id"] for m in _model_options()}
                if not isinstance(model, str) or model not in allowed:
                    return jsonify({"error": "Unknown preferred_model"}), 400
                settings.preferred_model = model

        # --- BYOK keys: {provider: key} sets, {provider: ""} (or null) removes ---
        if "byok" in data:
            byok = data.get("byok") or {}
            unknown = set(byok.keys()) - set(BYOK_PROVIDERS.keys())
            if unknown:
                return jsonify({"error": f"Unknown BYOK providers: {', '.join(sorted(unknown))}"}), 400
            user_keys = decrypt_api_keys(settings.byok_keys_enc)
            for provider, key in byok.items():
                env_var = BYOK_PROVIDERS[provider]["env_var"]
                if key is None or str(key).strip() == "":
                    user_keys.pop(env_var, None)
                else:
                    user_keys[env_var] = str(key).strip()
            settings.byok_keys_enc = encrypt_api_keys(user_keys) if user_keys else None

        session.commit()
        snapshot = {
            "default_mode": settings.default_mode or "deep",
            "preferred_model": settings.preferred_model,
            "byok_keys_enc": settings.byok_keys_enc,
        }
        user_snapshot = (user.email, user.username, user.first_name, user.last_name,
                         user.role, user.created_at)
        user_keys = decrypt_api_keys(snapshot["byok_keys_enc"])
        fake_user = type("U", (), {
            "email": user_snapshot[0], "username": user_snapshot[1],
            "first_name": user_snapshot[2], "last_name": user_snapshot[3],
            "role": user_snapshot[4], "created_at": user_snapshot[5],
        })()
    finally:
        session.close()
    fake_settings = type("S", (), snapshot)()
    return jsonify(_settings_payload(fake_user, fake_settings, user_keys))


def run_analysis(task_id: int, platform: str, profile_id: str, app=None, mode: str = "deep"):
    """Run analysis in background thread
    
    Args:
        task_id: ID of the task to process
        platform: Social media platform
        profile_id: Profile identifier
        app: Flask app instance (required for thread context)
    """
    if app is None:
        app = current_app._get_current_object()
    
    with app.app_context():
        # Force new database connection for this thread
        # SQLAlchemy connections are not thread-safe
        db.session.remove()  # Remove any existing session
        
        task = Task.query.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        # Install the owning user's BYOK keys + preferences for this run.
        # The task row carries the owner, so this works for the threaded
        # executor and for celery workers (separate process).
        from app.utils.config import set_user_context, reset_user_context
        _ctx_token = set_user_context(load_user_context(task.user_id))

        try:
            # Update task status
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.utcnow()
            task.progress = 10
            task.message = "Processing"
            db.session.commit()

            # Run the actual analysis
            result = analyzer.analyze_profile(platform, profile_id, mode=mode)

            # Canonical: persist in DB; file is best-effort fallback for debugging
            try:
                task.result_data = json.loads(json.dumps(result, default=str))
                task.has_result = True
            except Exception as e:
                logger.error(f"Failed to serialize result_data for task {task_id}: {e}", exc_info=True)
                task.result_data = None
                task.has_result = False

            # Optional: also write a file in development environments
            result_path = Path(current_app.config["RESULTS_FOLDER"]) / f"{task_id}.json"
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                with open(result_path, "w") as f:
                    json.dump(result, f, indent=2)
                task.result_path = str(result_path)
            except Exception:
                # File persistence is best-effort; DB persistence is canonical
                task.result_path = None

            # Record a comparable point-in-time snapshot. Runs that collected
            # nothing are skipped so a failed scrape never bends the trend line.
            try:
                from app.web.models.dossier import DossierSnapshot

                exists = DossierSnapshot.query.filter_by(task_id=task.id).first()
                if not exists:
                    snapshot = DossierSnapshot.build(
                        task_id=task.id,
                        platform=task.platform,
                        username=result.get("profile_info", {}).get("username") or task.profile_id,
                        result=result,
                        collection_mode=mode,
                    )
                    if snapshot is not None:
                        db.session.add(snapshot)
                        db.session.commit()
                        logger.info(
                            f"Stored snapshot {snapshot.id} for task {task.id} "
                            f"({task.platform}/{snapshot.username})"
                        )
            except Exception as snap_err:
                # History is additive: never fail a completed analysis over it.
                db.session.rollback()
                logger.error(f"Snapshot capture failed for task {task.id}: {snap_err}", exc_info=True)

            # Update task as complete
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.progress = 100
            task.message = "Completed"
            if task.started_at:
                task.duration = (task.completed_at - task.started_at).total_seconds()
            db.session.commit()

        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration = (task.completed_at - task.started_at).total_seconds()
            db.session.commit()
        finally:
            reset_user_context(_ctx_token)


def _provider_budget(mode: str) -> dict:
    """Describe whether the provider balance can cover one run of ``mode``.

    The number is the last value the provider reported, so it can be stale by
    one run; the check is deliberately conservative (block only below cost).
    """
    from app.core.scrape_client import RUN_CREDIT_ESTIMATES, read_credits

    observed = read_credits(current_app.config.get("PROVIDER_USAGE_PATH")) or {}
    remaining = observed.get("credits_remaining")
    needed = RUN_CREDIT_ESTIMATES.get(mode, RUN_CREDIT_ESTIMATES["deep"])
    if remaining is None:
        return {
            "known": False,
            "remaining": None,
            "needed": needed,
            "enough": True,  # unknown balance must not block a legitimate run
            "observed_at": None,
            "message": "Provider balance has not been reported yet in this install.",
        }
    enough = remaining >= needed
    return {
        "known": True,
        "remaining": remaining,
        "needed": needed,
        "enough": enough,
        "runs_left": int(remaining // needed),
        "observed_at": observed.get("observed_at"),
        "message": (
            f"{remaining} credit(s) remaining; this run needs about {needed}."
            if enough else
            f"Only {remaining} credit(s) remaining but this run needs about {needed}. "
            "Top up the data provider before starting it."
        ),
    }


@api_bp.route("/provider/usage", methods=["GET"])
def provider_usage():
    """Last observed provider balance and what the next runs would cost."""
    from app.core.scrape_client import RUN_CREDIT_ESTIMATES

    return jsonify({
        "scrapecreators": _provider_budget("deep"),
        "estimated_cost_per_run": RUN_CREDIT_ESTIMATES,
    })


@api_bp.route("/analyze", methods=["POST"])
def start_analysis():
    """Start a new profile analysis task"""
    data = request.get_json()

    if not data or "platform" not in data or "profile_id" not in data:
        return (
            jsonify({"error": "Missing required fields: platform and profile_id"}),
            400,
        )

    # Mode: explicit request value wins, else the user's saved default.
    mode = data.get("mode")
    if mode is None:
        mode = load_user_context(_uid())["default_mode"]
    if mode not in ("quick", "deep"):
        return jsonify({"error": "mode must be 'quick' or 'deep'"}), 400

    # Pre-flight: never start a run the provider balance cannot cover. The
    # failure mode this prevents is a half-collected dossier that looks like an
    # account with almost no content.
    budget = _provider_budget(mode)
    if not budget["enough"]:
        return jsonify({
            "error": "Insufficient data-provider credits",
            "detail": budget["message"],
            "budget": budget,
        }), 402

    # Create new task (Task.__init__ only accepts platform and profile_id)
    # user_id is passed through kwargs and stamped as the owner.
    task = Task(
        platform=data["platform"].lower(),
        profile_id=data["profile_id"],
        user_id=_uid(),
    )
    # Status is set to PENDING by default in __init__

    db.session.add(task)
    db.session.commit()

    # Start analysis
    # FIXED: Use threading by default for Railway single-service deployment.
    # Celery requires a separate worker service which adds complexity and cost.
    # Threading is sufficient for current scale and works immediately.
    # 
    # To enable Celery in future: set FORCE_CELERY=true environment variable
    # and deploy a separate Railway worker service.
    force_celery = os.getenv("FORCE_CELERY", "").lower() == "true"
    redis_url = os.getenv("REDIS_URL")
    task_started = False
    
    if force_celery and redis_url:
        logger.info(f"FORCE_CELERY enabled, attempting Celery enqueue for task {task.id}")
        try:
            from app.core.tasks import run_task_analysis
            run_task_analysis.delay(task.id)
            task_started = True
            logger.info(f"Task {task.id} enqueued to Celery successfully")
        except Exception as e:
            logger.error(f"Failed to enqueue Celery task {task.id}: {e}", exc_info=True)
            logger.info(f"Falling back to threading for task {task.id}")
    
    if not task_started:
        # Use threading (default for Railway deployment without worker service)
        logger.info(f"Starting task {task.id} in background thread")
        try:
            # Pass app instance to thread for context
            app_instance = current_app._get_current_object()
            thread = threading.Thread(
                target=run_analysis, 
                args=(task.id, task.platform, task.profile_id, app_instance, mode)
            )
            thread.daemon = True
            thread.start()
            task_started = True
            logger.info(f"Task {task.id} started in background thread successfully")
        except Exception as e:
            logger.error(f"Failed to start background thread for task {task.id}: {e}", exc_info=True)
            # Update task as failed
            task.status = TaskStatus.FAILED
            task.error = f"Failed to start analysis: {str(e)}"
            db.session.commit()
            return (jsonify({
                "error": "Failed to start analysis task",
                "details": str(e),
                "task": task.to_dict()
            }), 500)

    return (jsonify({"message": "Analysis task created", "task": task.to_dict()}), 202)


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """Get task status and details"""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task.to_dict())


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    """Erase a run and everything derived from it, including snapshots.

    Erasure has to be real to mean anything: the collected posts, the dossier and
    the subject's history entries all go, because a retained snapshot still
    contains the subject's engagement data. Only finished work can be deleted;
    a run in flight must be cancelled first so the worker cannot rewrite it.
    """
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        return jsonify({"error": "Cancel the run before deleting it"}), 409

    from app.web.models import DossierSnapshot

    snapshots = DossierSnapshot.query.filter_by(task_id=task.id).delete()
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted", "task_id": task_id, "snapshots_deleted": snapshots})


@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    """List all tasks with optional filtering"""
    # Get query parameters
    platform = request.args.get("platform")
    status = request.args.get("status")
    limit = request.args.get("limit", type=int, default=10)
    offset = request.args.get("offset", type=int, default=0)

    # Build query (scoped to the authenticated user)
    query = Task.query.filter_by(user_id=_uid())

    if platform:
        query = query.filter_by(platform=platform.lower())
    if status:
        try:
            # TaskStatus values are lowercase ("pending", "processing", ...)
            task_status = TaskStatus(status.lower())
            query = query.filter_by(status=task_status)
        except ValueError:
            return jsonify({"error": f"Invalid status: {status}"}), 400

    # Get total count
    total = query.count()

    # Apply pagination
    tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()

    return jsonify(
        {
            "tasks": [task.to_dict() for task in tasks],
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    )


@api_bp.route("/tasks/<int:task_id>/status", methods=["GET"])
def get_task_status(task_id):
    """Get task status only - for polling"""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(
        {
            "id": task.id,
            "status": task.status.value,
            "progress": task.progress,
            "message": task.message,
            "error": task.error,
        }
    )


@api_bp.route("/tasks/<int:task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    """Cancel a pending or processing task"""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    if task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        msg = "Can only cancel pending or processing tasks"
        return jsonify({"error": msg}), 400

    task.status = TaskStatus.FAILED
    task.error = "Task cancelled by user"
    task.completed_at = datetime.utcnow()
    if task.started_at:
        task.duration = (task.completed_at - task.started_at).total_seconds()
    db.session.commit()

    return jsonify({"message": "Task cancelled", "task": task.to_dict()})


@api_bp.route("/tasks/<int:task_id>/retry", methods=["POST"])
def retry_task(task_id):
    """Retry a stuck or failed task using threading (bypass Celery)"""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    # Only allow retrying pending, failed, or stuck processing tasks
    if task.status not in [TaskStatus.PENDING, TaskStatus.FAILED, TaskStatus.PROCESSING]:
        msg = "Can only retry pending, failed, or processing tasks"
        return jsonify({"error": msg}), 400

    logger.info(f"Retrying task {task.id} (status: {task.status.value})")
    
    # Reset task to pending state
    task.status = TaskStatus.PENDING
    task.error = None
    task.started_at = None
    task.completed_at = None
    task.progress = 0
    task.message = "Retrying"
    db.session.commit()

    # Start task using threading (force bypass Celery)
    try:
        # Pass app instance to thread for context
        app_instance = current_app._get_current_object()
        thread = threading.Thread(
            target=run_analysis, 
            args=(task.id, task.platform, task.profile_id, app_instance)
        )
        thread.daemon = True
        thread.start()
        logger.info(f"Task {task.id} retry started in background thread")
        return jsonify({"message": "Task retry started", "task": task.to_dict()}), 200
    except Exception as e:
        logger.error(f"Failed to retry task {task.id}: {e}", exc_info=True)
        task.status = TaskStatus.FAILED
        task.error = f"Failed to retry: {str(e)}"
        db.session.commit()
        return jsonify({"error": "Failed to retry task", "details": str(e)}), 500


def _subject_snapshots(task, limit=12):
    """Snapshots of the same subject (owner + platform + resolved identity).

    Matching only on the requested identifier split a single account into two
    timelines whenever it was looked up by handle in one run and by numeric id
    in another. Identity is therefore the resolved username (or the requested
    id, for runs whose username could not be resolved). Owner scoping lives in
    the join, so one tenant never sees another's timeline.
    """
    from app.web.models.dossier import DossierSnapshot
    from sqlalchemy import func, or_

    requested = (task.profile_id or "").lower()
    query = (
        db.session.query(DossierSnapshot.snapshot_data, DossierSnapshot.created_at,
                         DossierSnapshot.task_id, DossierSnapshot.collection_mode,
                         DossierSnapshot.id, DossierSnapshot.username)
        .join(Task, Task.id == DossierSnapshot.task_id)
        .filter(Task.platform == task.platform)
        .filter(or_(
            func.lower(DossierSnapshot.username) == requested,
            func.lower(Task.profile_id) == requested,
        ))
    )
    query = (query.filter(Task.user_id.is_(None)) if task.user_id is None
             else query.filter(Task.user_id == task.user_id))
    rows = query.order_by(DossierSnapshot.created_at.asc()).all()
    if not rows and task.profile_id:
        # Nothing matched on identity: fall back to the resolved username of
        # this task's own snapshot so a rename still yields its own timeline.
        own = DossierSnapshot.query.filter_by(task_id=task.id).first()
        if own is not None:
            query = (db.session.query(DossierSnapshot.snapshot_data, DossierSnapshot.created_at,
                                      DossierSnapshot.task_id, DossierSnapshot.collection_mode,
                                      DossierSnapshot.id, DossierSnapshot.username)
                     .join(Task, Task.id == DossierSnapshot.task_id)
                     .filter(Task.platform == task.platform)
                     .filter(func.lower(DossierSnapshot.username) == (own.username or "").lower()))
            query = (query.filter(Task.user_id.is_(None)) if task.user_id is None
                     else query.filter(Task.user_id == task.user_id))
            rows = query.order_by(DossierSnapshot.created_at.asc()).all()
    return rows[-limit:]


def _with_history(task, payload):
    """Attach this subject's timeline and the change since the previous run."""
    from app.web.models.dossier import DossierSnapshot

    if not isinstance(payload, dict):
        return payload
    try:
        rows = _subject_snapshots(task)
    except Exception as e:  # history must never break result delivery
        logger.error(f"History lookup failed for task {task.id}: {e}", exc_info=True)
        return payload
    if not rows:
        return payload

    history = [
        {
            "snapshot_id": row.id,
            "task_id": row.task_id,
            "collected_at": row.created_at.isoformat() if row.created_at else None,
            "mode": row.collection_mode,
            "followers": (row.snapshot_data or {}).get("followers"),
            "engagement_rate_percent": (row.snapshot_data or {}).get("engagement_rate_percent"),
            "posts_measured": (row.snapshot_data or {}).get("posts_measured"),
            "bot_likelihood": (row.snapshot_data or {}).get("bot_likelihood"),
            "trust_score": (row.snapshot_data or {}).get("trust_score"),
            "risk_assessment": (row.snapshot_data or {}).get("risk_assessment"),
            "political_label": (row.snapshot_data or {}).get("political_label"),
        }
        for row in rows
    ]

    out = dict(payload)
    out["history"] = {
        "count": len(history),
        "snapshots": history,
        "first_collected_at": history[0]["collected_at"],
        "latest_collected_at": history[-1]["collected_at"],
    }
    if len(history) >= 2:
        previous, current = rows[-2], rows[-1]
        delta = DossierSnapshot.compute_delta(current.snapshot_data, previous.snapshot_data)
        delta["from_task_id"] = previous.task_id
        delta["to_task_id"] = current.task_id
        try:
            times = [r.created_at for r in rows[-2:] if r.created_at]
            delta["elapsed_hours"] = round((times[-1] - times[-2]).total_seconds() / 3600, 1) if len(times) == 2 else None
        except Exception:
            delta["elapsed_hours"] = None
        out["changes"] = delta
    return out


@api_bp.route("/tasks/<int:task_id>/results", methods=["GET"])
def get_results(task_id):
    """Get analysis results for a completed task"""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    if task.status != TaskStatus.COMPLETED:
        msg = "Results only available for completed tasks"
        return jsonify({"error": msg}), 400

    # Canonical source: DB
    # Canonical source: DB - Only check if attribute exists (compatibility)
    if hasattr(task, 'result_data') and task.result_data is not None:
        return jsonify(_with_history(task, task.result_data))

    # Backward-compatible fallback: file
    if task.result_path and Path(task.result_path).exists():
        try:
            with open(task.result_path, "r") as f:
                results = json.load(f)
            return jsonify(_with_history(task, results))
        except Exception as e:
            logger.error(f"Error reading results for task {task_id}: {e}")

    # If no data found, return empty structure to prevent frontend errors
    return jsonify({
        "profile_info": {
            "username": task.profile_id,
            "followers": 0,
            "following": 0, 
            "posts": 0
        },
        "sentiment": {
            "overall": "neutral",
            "positive": 0,
            "neutral": 100,
            "negative": 0
        },
        "content_analysis": {},
        "authenticity": {},
        "predictions": {},
        "metadata": {
            "error": "No result data available"
        }
    })


@api_bp.route("/tasks/<int:task_id>/download", methods=["GET"])
def download_results(task_id):
    """Download task results as a file (JSON or HTML Dossier)"""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    output_format = request.args.get('format', 'json').lower()

    if task.status != TaskStatus.COMPLETED:
        msg = "Can only download results for completed tasks"
        return jsonify({"error": msg}), 400

    # Get data (canonical: DB; fallback: file)
    data = task.result_data if getattr(task, 'result_data', None) is not None else None

    if data is None and task.result_path and Path(task.result_path).exists():
        with open(task.result_path, "r") as f:
            data = json.load(f)

    if not data:
        print("DEBUG: Result data is empty/None")
        return jsonify({"error": "Results not found"}), 404
    
    print(f"DEBUG: Result data type: {type(data)}")
    # print(f"DEBUG: Result data keys: {data.keys() if isinstance(data, dict) else 'Not Dict'}")

    # HTML Dossier Export
    # HTML Dossier Export
    if output_format in ['html', 'pdf']:
        try:
            from app.core.report_generator import DossierReportGenerator
            generator = DossierReportGenerator()
            # Pass dictionary directly
            html_content = generator.generate_html_report(data)
            
            return current_app.response_class(
                html_content,
                mimetype="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename=dossier_{task.profile_id}.html"
                }
            )
        except Exception as e:
            print(f"DEBUG: HTML generation error: {e}")
            return jsonify({"error": f"Report generation failed: {e}", "details": str(e)}), 500

    # Default JSON Export
    try:
        payload = json.dumps(data, indent=2, default=str)
    except Exception as e:
        print(f"DEBUG: JSON serialization error: {e}")
        return jsonify({"error": f"Serialization error: {e}"}), 500

    return current_app.response_class(
        payload,
        mimetype="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=analysis_{task.platform}_{task.profile_id}.json"
        },
    )


@api_bp.route("/stats/platform-distribution", methods=["GET"])
def platform_distribution():
    """Get platform distribution statistics"""
    platform_stats = (
        db.session.query(Task.platform, db.func.count(Task.id).label("count"))
        .filter(Task.user_id == _uid())
        .group_by(Task.platform)
        .all()
    )

    return jsonify(
        [{"platform": platform, "count": count} for platform, count in platform_stats]
    )


@api_bp.route("/stats/completion-rate", methods=["GET"])
def completion_rate():
    """Get task completion rate statistics"""
    total = Task.query.filter_by(user_id=_uid()).count()
    completed = Task.query.filter_by(user_id=_uid(), status=TaskStatus.COMPLETED).count()
    failed = Task.query.filter_by(user_id=_uid(), status=TaskStatus.FAILED).count()

    return jsonify(
        {
            "total": total,
            "completed": completed,
            "failed": failed,
            "completion_rate": (completed / total if total > 0 else 0) * 100,
        }
    )


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Docker/Kubernetes"""
    try:
        # Check database connection
        db.session.execute(db.text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return jsonify({
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


# =============================================================================
# Verification (Product B) — consolidated into Product A Flask app (no new files)
# =============================================================================
# Reuses existing CLIs/engines: ingestor, claim_extractor, fact_check, temporal,
# rag, confidence. No Product A behaviour is removed.

def _verification_payload(post=None, claim=None, vr=None):
    out = {}
    if post is not None:
        out["post"] = {
            "id": post.id,
            "platform": str(getattr(post, "platform", "")),
            "profile_id": getattr(post, "profile_id", None),
            "text": (getattr(post, "text", None) or getattr(post, "content", None) or "")[:500],
            "language": getattr(getattr(post, "detected_language", None), "value", str(getattr(post, "detected_language", None))),
            "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
        }
    if claim is not None:
        out["claim"] = {
            "id": claim.id,
            "post_id": claim.post_id,
            "text": (claim.claim_text or "")[:500],
            "type": getattr(getattr(claim, "claim_type", None), "value", str(getattr(claim, "claim_type", None))),
            "checkworthiness": getattr(claim, "check_worthiness_score", None),
            "entities": getattr(claim, "entities", None),
        }
    if vr is not None:
        status_val = None
        if getattr(vr, "verification_status", None) is not None:
            status_val = getattr(vr.verification_status, "value", str(vr.verification_status))
        out["verification"] = {
            "id": vr.id,
            "claim_id": vr.claim_id,
            "status": status_val or vr.status,
            "confidence": vr.confidence_score,
            "composite": vr.composite_verification_score,
            "fact_check_verdict": vr.fact_check_verdict,
            "completed_at": vr.completed_at.isoformat() if getattr(vr, "completed_at", None) else None,
            "evidence_chain_layers": list((vr.evidence_chain or {}).keys()),
        }
    return out


def _run_claim_pipeline(claim):
    """Run Layers 4->5->6->7 for one claim; returns dict of stage outcomes."""
    summary = {"claim_id": claim.id, "layers": {}}
    # Layer 4: Fact-check
    try:
        from app.core.fact_check.engine import FactCheckEngine
        engine = FactCheckEngine()
        vr = engine.process_claim(claim)
        summary["layers"]["fact_check"] = bool(vr)
    except Exception as e:
        logger.error(f"Layer4 failed claim {claim.id}: {e}", exc_info=True)
        summary["layers"]["fact_check_error"] = str(e)
    # Layer 5: Temporal
    try:
        from app.core.temporal_verification.verifier import TemporalVerifier
        verifier = TemporalVerifier()
        res5 = verifier.process_claim(claim)
        summary["layers"]["temporal"] = bool(res5)
    except Exception as e:
        logger.error(f"Layer5 failed claim {claim.id}: {e}", exc_info=True)
        summary["layers"]["temporal_error"] = str(e)
    # Layer 6: RAG (LLM) — best effort, skips cleanly without evidence/key
    try:
        from app.core.rag_analysis.rag_engine import RAGEngine
        rag = RAGEngine()
        res6 = rag.process_claim(claim)
        summary["layers"]["rag"] = bool(res6)
    except Exception as e:
        logger.error(f"Layer6 failed claim {claim.id}: {e}", exc_info=True)
        summary["layers"]["rag_error"] = str(e)
    # Layer 7: Confidence scoring — writes composite + human-review flag into chain
    try:
        from app.web.models.verification import VerificationResult as VR
        from app.core.evidence.confidence_scorer import ConfidenceScorer
        vr = db.session.query(VR).filter_by(claim_id=claim.id).first()
        if vr:
            scorer = ConfidenceScorer()
            scored = scorer.score_verification(vr)
            vr.composite_verification_score = scored["confidence_score"]
            if not vr.evidence_chain:
                vr.evidence_chain = {}
            # Reassign (not in-place mutate): SQLAlchemy JSON columns don't detect
            # in-place dict mutation, so layer_7 would be lost on commit.
            vr.evidence_chain = {
                **vr.evidence_chain,
                "layer_7": {
                    "verdict": scored["verdict"],
                    "needs_human_review": scored["needs_human_review"],
                    "breakdown": scored["breakdown"],
                    "scored_at": scored["scored_at"],
                }
            }
            db.session.commit()
            summary["layers"]["confidence"] = scored["verdict"]
    except Exception as e:
        logger.error(f"Layer7 failed claim {claim.id}: {e}", exc_info=True)
        summary["layers"]["confidence_error"] = str(e)
    return summary


@api_bp.route("/verification/post", methods=["POST"])
def create_verification_post():
    """Manual ingest: create a SocialMediaPost (Product B Layer 0-2 entry)."""
    data = request.get_json() or {}
    text = (data.get("text") or data.get("content") or "").strip()
    platform = (data.get("platform") or "facebook").lower()
    profile_id = data.get("profile_id") or data.get("author_id") or "unknown"
    if not text:
        return jsonify({"error": "Missing 'text' (claim source)"}), 400
    from app.web.models.verification import SocialMediaPost, LanguageCode, MediaType
    from app.core.ingestion.lang_detect import detect_language
    import hashlib
    lang_code, lang_conf = detect_language(text)
    lang = LanguageCode.EN if lang_code == "en" else (LanguageCode.BN if lang_code == "bn" else LanguageCode.UNKNOWN)
    post_id = data.get("id") or f"{platform}_{hashlib.md5(text.encode()).hexdigest()[:12]}"
    post = db.session.query(SocialMediaPost).filter_by(id=post_id).first()
    if post and post.user_id != _uid():
        # Post id already belongs to another user: don't leak or overwrite it
        return jsonify({"error": "Post not found"}), 404
    if not post:
        post = SocialMediaPost(
            id=post_id,
            user_id=_uid(),
            platform=platform,
            profile_id=profile_id,
            text=text,
            content=text,
            text_hash=hashlib.md5(text.encode()).hexdigest()[:32],  # stable; hash() is per-process salted
            detected_language=lang,
            detected_language_confidence=lang_conf,
            author_id=data.get("author_id", profile_id),
            author_name=data.get("author_name", ""),
            author_profile_url=data.get("author_profile_url", ""),
            media_type=MediaType.TEXT,
            post_url=data.get("post_url", ""),
            created_at_platform=datetime.utcnow(),
            raw_data={"source": "manual", "submitted": datetime.utcnow().isoformat()},
        )
        db.session.add(post)
    else:
        # upsert text if new content
        if text and (post.text or post.content) != text:
            post.text = text
            post.content = text
    db.session.commit()
    return jsonify({"message": "Post created", **_verification_payload(post=post)}), 201


@api_bp.route("/verification/post/from-task/<int:task_id>", methods=["POST"])
def create_post_from_task(task_id):
    """Bridge: Product A Task -> Product B SocialMediaPost (consolidation)."""
    task = _own_task(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    if not getattr(task, "has_result", False) or not getattr(task, "result_data", None):
        # try file fallback
        data = None
        if task.result_path and Path(task.result_path).exists():
            try:
                with open(task.result_path) as f:
                    data = json.load(f)
            except Exception:
                data = None
        if not data:
            return jsonify({"error": "Task has no result_data yet (run /analyze first)"}), 400
        result = data
    else:
        result = task.result_data
    from app.web.models.verification import SocialMediaPost, LanguageCode, MediaType
    import hashlib
    profile_info = result.get("profile_info", {}) if isinstance(result, dict) else {}
    executive = result.get("executive_summary", "") if isinstance(result, dict) else ""
    bio = profile_info.get("bio", "") if isinstance(profile_info, dict) else ""
    display = profile_info.get("display_name", "") if isinstance(profile_info, dict) else ""
    # Synthesise a verifiable text blob from the dossier (keeps both products linked)
    text_parts = []
    if display:
        text_parts.append(f"{display} is a creator on {task.platform}.")
    if bio:
        text_parts.append(bio)
    if executive:
        text_parts.append(str(executive)[:800])
    # Content analysis claims add numbers/dates that the extractor can use
    content_analysis = result.get("content_analysis", {}) if isinstance(result, dict) else {}
    if isinstance(content_analysis, dict):
        for k, v in list(content_analysis.items())[:5]:
            if isinstance(v, str) and len(v) > 20:
                text_parts.append(f"{k}: {v[:300]}")
    text = " ".join(text_parts).strip() or f"Profile {task.profile_id} on {task.platform}."
    post_id = f"{task.platform}_{task.profile_id}_{hashlib.md5(text.encode()).hexdigest()[:10]}"
    existing = db.session.query(SocialMediaPost).filter_by(id=post_id).first()
    if existing:
        return jsonify({"message": "Post already exists", **_verification_payload(post=existing)}), 200
    post = SocialMediaPost(
        id=post_id,
        user_id=_uid(),
        platform=task.platform,
        profile_id=task.profile_id,
        text=text,
        content=text,
        author_id=task.profile_id,
        author_name=display,
        detected_language=LanguageCode.EN,
        media_type=MediaType.TEXT,
        created_at_platform=task.completed_at or datetime.utcnow(),
        raw_data={"product": "A", "task_id": task_id, "result_keys": list(result.keys()) if isinstance(result, dict) else []},
    )
    db.session.add(post)
    db.session.commit()
    return jsonify({"message": "Post created from task", **_verification_payload(post=post)}), 201


@api_bp.route("/verification/posts", methods=["GET"])
def list_verification_posts():
    from app.web.models.verification import SocialMediaPost
    limit = request.args.get("limit", type=int, default=20)
    posts = db.session.query(SocialMediaPost).filter_by(user_id=_uid()).order_by(SocialMediaPost.created_at.desc()).limit(limit).all()
    return jsonify({"posts": [_verification_payload(post=p) for p in posts], "total": len(posts)})


@api_bp.route("/verification/claims", methods=["GET"])
def list_verification_claims():
    from app.web.models.verification import Claim, SocialMediaPost
    limit = request.args.get("limit", type=int, default=20)
    claims = (db.session.query(Claim).join(SocialMediaPost, Claim.post_id == SocialMediaPost.id)
              .filter(SocialMediaPost.user_id == _uid())
              .order_by(Claim.extracted_at.desc()).limit(limit).all())
    return jsonify({"claims": [_verification_payload(claim=c)["claim"] for c in claims], "total": len(claims)})


@api_bp.route("/verification/claim/<claim_id>", methods=["GET"])
def get_verification_claim(claim_id):
    from app.web.models.verification import Claim, VerificationResult
    claim = db.session.query(Claim).filter_by(id=claim_id).first()
    if not claim:
        return jsonify({"error": "Claim not found"}), 404
    from app.web.models.verification import SocialMediaPost as _SMP
    post = db.session.query(_SMP).filter_by(id=claim.post_id).first()
    if post is None or post.user_id != _uid():
        return jsonify({"error": "Claim not found"}), 404
    vr = db.session.query(VerificationResult).filter_by(claim_id=claim.id).first()
    return jsonify(_verification_payload(claim=claim, vr=vr))


@api_bp.route("/verification/claim/<claim_id>/review", methods=["POST"])
def review_verification_claim(claim_id):
    """Human review: approve or override a claim's verdict.
    Body: { "verdict": "VERIFIED_TRUE|VERIFIED_FALSE|MISLEADING|UNVERIFIABLE",
            "action": "approve|override" (default override),
            "reviewer": str, "note": str }
    Closes the gap where needs_human_review was set but human_override
    could never be written (always None).
    """
    from app.web.models.verification import Claim, VerificationResult, VerificationStatus
    claim = db.session.query(Claim).filter_by(id=claim_id).first()
    if not claim:
        return jsonify({"error": "Claim not found"}), 404
    from app.web.models.verification import SocialMediaPost as _SMP2
    _post = db.session.query(_SMP2).filter_by(id=claim.post_id).first()
    if _post is None or _post.user_id != _uid():
        return jsonify({"error": "Claim not found"}), 404
    vr = db.session.query(VerificationResult).filter_by(claim_id=claim.id).first()
    if not vr:
        return jsonify({"error": "No verification result yet for this claim (run the pipeline first)"}), 404
    data = request.get_json() or {}
    verdict = str(data.get("verdict", "")).upper()
    from app.web.models.verification import _coerce_status
    target = _coerce_status(verdict)
    if target is None:
        return jsonify({"error": f"Invalid verdict '{verdict}'. Use VERIFIED_TRUE, VERIFIED_FALSE, MISLEADING or UNVERIFIABLE"}), 400
    action = str(data.get("action", "override")).lower()
    if action not in ("approve", "override"):
        return jsonify({"error": "action must be 'approve' or 'override'"}), 400
    review = {
        "verdict": target.value,
        "action": action,
        "reviewer": data.get("reviewer", ""),
        "note": data.get("note", ""),
        "reviewed_at": datetime.utcnow().isoformat(),
    }
    chain = vr.evidence_chain or {}
    layer7 = dict(chain.get("layer_7", {}))
    layer7["human_override"] = review
    layer7["needs_human_review"] = False
    vr.evidence_chain = {**chain, "layer_7": layer7}  # reassign: JSON mutation isn't tracked
    if action == "override":
        vr.verification_status = target
        vr.status = target.value
        vr.fact_check_verdict = target.value
    db.session.commit()
    return jsonify({"message": f"Human review recorded ({action})", "claim_id": claim.id,
                    "human_override": review, "verification_status": vr.status,
                    "needs_human_review": False})


@api_bp.route("/verification/results", methods=["GET"])
def list_verification_results():
    from app.web.models.verification import VerificationResult, Claim, SocialMediaPost
    limit = request.args.get("limit", type=int, default=20)
    rows = (db.session.query(VerificationResult)
            .join(Claim, VerificationResult.claim_id == Claim.id)
            .join(SocialMediaPost, Claim.post_id == SocialMediaPost.id)
            .filter(SocialMediaPost.user_id == _uid())
            .order_by(VerificationResult.created_at.desc()).limit(limit).all())
    return jsonify({"results": [_verification_payload(vr=r)["verification"] for r in rows], "total": len(rows)})


@api_bp.route("/verification/pipeline", methods=["POST"])
def run_verification_pipeline():
    """Run full 7-layer pipeline for a post or batch of unprocessed posts.
    Body (optional): { "post_id": str, "limit": int, "max_claims": int }
    """
    data = request.get_json() or {}
    limit = int(data.get("limit", 50))
    summaries = []
    # 1) Claim extraction for unprocessed posts (or a specific post)
    from app.core.claim_extraction.extractor import ClaimExtractor
    from app.web.models.verification import SocialMediaPost, Claim
    extractor = ClaimExtractor()
    if data.get("post_id"):
        post = _own_post(data["post_id"])
        if not post:
            return jsonify({"error": "Post not found"}), 404
        claims = extractor.extract_claims_from_post(post)
        summaries.append({"stage": "extract", "post_id": post.id, "claims": len(claims)})
    else:
        # Batch mode scoped to the caller's own unprocessed posts only
        # (extractor.process_unprocessed_posts would process everyone's).
        own_posts = (db.session.query(SocialMediaPost)
                     .filter_by(user_id=_uid(), processed_for_claims=False)
                     .limit(limit).all())
        extracted = 0
        for p in own_posts:
            extracted += len(extractor.extract_claims_from_post(p))
        summaries.append({"stage": "extract", "processed_posts": len(own_posts), "claims_extracted": extracted})
    # 2-4) Fact-check -> temporal -> RAG -> confidence for claims lacking verification
    from app.web.models.verification import VerificationResult
    claims = (db.session.query(Claim).join(SocialMediaPost, Claim.post_id == SocialMediaPost.id)
              .filter(SocialMediaPost.user_id == _uid()).limit(limit).all())
    for claim in claims:
        vr = db.session.query(VerificationResult).filter_by(claim_id=claim.id).first()
        if vr and vr.evidence_chain and "layer_4" in vr.evidence_chain and "layer_7" in vr.evidence_chain:
            continue
        summaries.append(_run_claim_pipeline(claim))
    return jsonify({"message": "Verification pipeline complete", "summaries": summaries}), 200


@api_bp.route("/verification/task/<int:task_id>/run", methods=["POST"])
def verify_task(task_id):
    """One-call bridge: Task -> Post -> Pipeline (Product A result verified by Product B)."""
    # reuse from-task bridge then pipeline
    create_resp = create_post_from_task(task_id)
    # create_post_from_task returns (response, status) — handle both
    if isinstance(create_resp, tuple):
        resp, code = create_resp
        if code >= 400:
            return resp
        # parse post id
        payload = resp.get_json()
    else:
        payload = create_resp.get_json()
    post_id = payload.get("post", {}).get("id")
    # run pipeline scoped to this post
    return run_verification_pipeline_scoped(post_id)


def run_verification_pipeline_scoped(post_id=None):
    from app.core.claim_extraction.extractor import ClaimExtractor
    from app.web.models.verification import SocialMediaPost, Claim
    extractor = ClaimExtractor()
    post = _own_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    claims = extractor.extract_claims_from_post(post)
    summaries = []
    for claim in claims:
        summaries.append(_run_claim_pipeline(claim))
    return jsonify({"message": "Task verification complete", "post_id": post_id, "claims": len(claims), "summaries": summaries}), 200


@api_bp.route("/apify/health", methods=["GET"])
def apify_health():
    """Check Apify token validity without running an Actor (no cost)."""
    from app.core.scrape_client import get_apify_client
    return jsonify(get_apify_client().check_token())


@api_bp.route("/apify/run", methods=["POST"])
def apify_run():
    """Run an Apify Actor synchronously and return dataset items.
    Body: {"actor": "clockworks/tiktok-scraper", "input": {...}}  OR
          {"platform": "tiktok", "username": "xxx"}  (uses mapped actor)
    NOTE: this spends Apify credits per run."""
    data = request.get_json() or {}
    from app.core.scrape_client import get_apify_client, ApifyError
    client = get_apify_client()
    if not client.is_configured:
        return jsonify({"error": "APIFY_API_TOKEN not configured", "configured": False}), 503
    try:
        if data.get("actor"):
            items = client.run_actor(data["actor"], data.get("input") or {})
            return jsonify({"actor": data["actor"], "count": len(items) if isinstance(items, list) else 0, "items": items})
        if data.get("platform") and data.get("username"):
            return jsonify(client.scrape_profile(data["platform"], data["username"], int(data.get("max_results", 20))))
        return jsonify({"error": "Provide {'actor','input'} or {'platform','username'}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)[:500]}), 502


@api_bp.route("/platforms", methods=["GET"])
def list_platforms():
    """List all supported social media platforms"""
    # All platforms supported by ScrapeCreators (except Truth Social)
    platforms = [
        {"id": "twitter", "name": "Twitter/X", "category": "social"},
        {"id": "instagram", "name": "Instagram", "category": "social"},
        {"id": "tiktok", "name": "TikTok", "category": "social"},
        {"id": "youtube", "name": "YouTube", "category": "video"},
        {"id": "linkedin", "name": "LinkedIn", "category": "professional"},
        {"id": "facebook", "name": "Facebook", "category": "social"},
        {"id": "reddit", "name": "Reddit", "category": "social"},
        {"id": "pinterest", "name": "Pinterest", "category": "social"},
        {"id": "snapchat", "name": "Snapchat", "category": "social"},
        {"id": "threads", "name": "Threads", "category": "social"},
        {"id": "bluesky", "name": "Bluesky", "category": "social"},
        {"id": "twitch", "name": "Twitch", "category": "streaming"},
        {"id": "kick", "name": "Kick", "category": "streaming"},
        {"id": "github", "name": "GitHub", "category": "developer"},
        {"id": "linktree", "name": "Linktree", "category": "links"},
        {"id": "komi", "name": "Komi", "category": "links"},
        {"id": "pillar", "name": "Pillar", "category": "links"},
        {"id": "linkbio", "name": "Linkbio", "category": "links"},
        {"id": "google", "name": "Google", "category": "search"},
        {"id": "tiktok_shop", "name": "TikTok Shop", "category": "commerce"},
        {"id": "amazon_shop", "name": "Amazon Shop", "category": "commerce"},
    ]
    
    return jsonify({
        "platforms": platforms,
        "total": len(platforms),
        "categories": list(set(p["category"] for p in platforms))
    })
