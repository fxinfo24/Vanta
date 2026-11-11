"""Vanta Celery tasks.

This module is the CANONICAL Celery configuration and task entrypoint.
Used by `scripts/start_celery.sh` locally and Railway worker service in production.

⚠️  IMPORTANT: This is the SOURCE OF TRUTH for Celery configuration.
    Any other Celery config files are deprecated/unused.

Design goals:
- Operate on the same `Task` table used by the Flask API (`app.web.models.Task`).
- Be safe to run as a separate process (Celery worker) in production.
- Gracefully handle Flask app context for database operations.
- Support both local Redis and Railway Redis services.

How to run:
- Local web: `python3 bin/run.py --web`
- Local worker: `celery -A app.core.tasks worker --loglevel=info --queues=analysis`
- Railway web: Auto-deployed via Procfile "web" command
- Railway worker: Separate Railway service using Procfile "worker" command
  * Uses --pool=solo to avoid mmap dependency issues in containerized environments

Environment requirements:
- REDIS_URL: Redis connection string (required for Celery)
- DATABASE_URI: PostgreSQL connection (Railway auto-provides)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from celery import Celery

from app.core.analyzer import SocialMediaAnalyzer
from app.web.app import create_app
from celery.schedules import crontab

from app.web.models import db, Task, TaskStatus

# Celery application
celery_app = Celery(
    "vanta",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

# Alias used by `celery -A app.core.tasks worker`
app = celery_app

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.core.tasks.run_task_analysis": {"queue": "analysis"},
        "app.core.tasks.run_verification_task": {"queue": "analysis"},
        "app.core.tasks.purge_expired_data": {"queue": "data"},
    },
    # Retention has to run without anyone remembering to run it. Daily is enough
    # for windows measured in tens of days.
    beat_schedule={
        "purge-expired-data": {
            "task": "app.core.tasks.purge_expired_data",
            "schedule": crontab(hour=3, minute=17),
        },
    },
)


@celery_app.task(name="app.core.tasks.purge_expired_data")
def purge_expired_data() -> Dict[str, int]:
    """Delete posts and quote receipts past their configured retention window."""
    from app.utils.config import retention_days
    from app.web.models.dossier import purge_expired_results, purge_expired_cache

    flask_app = create_app()
    with flask_app.app_context():
        windows = retention_days()
        result = purge_expired_results(
            db.session,
            raw_days=windows["raw_content_days"],
            quote_days=windows["quote_receipt_days"],
        )
        # Cached dossiers hold raw post text too, so they expire with the
        # retention sweep rather than lingering past their own TTL.
        result["cache_purged"] = purge_expired_cache(db.session)
        logger.info(f"Retention purge: {result} (windows={windows})")
        return result


def _save_results_to_file(flask_app, task_id: int, result: Dict[str, Any]) -> str:
    results_dir = Path(flask_app.config["RESULTS_FOLDER"])
    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / f"{task_id}.json"

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    return str(result_path)


def run_verification_for_posts(post_ids: List[str], max_claims: int = 20) -> List[Dict[str, Any]]:
    """Layers 3-7 for the given posts. Runs outside a request context.

    A claim costs four layers (fact-check, temporal, RAG, confidence) and takes
    tens of seconds each, so a dossier of posts cannot be verified inside the
    HTTP request that asked for it -- Render's request timeout cuts it off. The
    loop lives here so the Celery worker and the fallback thread run the exact
    same code. `_run_claim_pipeline` stays the single implementation of one
    claim's pipeline and is imported lazily to avoid an import cycle.
    """
    from app.web.routes.api import _run_claim_pipeline
    from app.web.models.verification import SocialMediaPost, VerificationResult
    from app.core.claim_extraction.extractor import ClaimExtractor

    extractor = ClaimExtractor()
    summaries: List[Dict[str, Any]] = []
    remaining = max(0, int(max_claims))

    for post_id in post_ids or []:
        if remaining <= 0:
            break
        post = db.session.query(SocialMediaPost).filter_by(id=post_id).first()
        if post is None:
            continue
        try:
            claims = extractor.extract_claims_from_post(post)
        except Exception as exc:
            logger.error(f"Claim extraction failed for post {post_id}: {exc}", exc_info=True)
            summaries.append({"post_id": post_id, "error": str(exc)})
            continue
        for claim in claims:
            if remaining <= 0:
                break
            done = db.session.query(VerificationResult).filter_by(claim_id=claim.id).first()
            if done and (done.evidence_chain or {}).get("layer_4") and (done.evidence_chain or {}).get("layer_7"):
                continue  # already verified end to end
            summaries.append(_run_claim_pipeline(claim))
            remaining -= 1
    return summaries


@celery_app.task(name="app.core.tasks.run_verification_task", bind=True)
def run_verification_task(self, post_ids: List[str], max_claims: int = 20) -> Dict[str, Any]:
    """Verify posts in a worker so the HTTP request can return immediately."""
    flask_app = create_app()
    with flask_app.app_context():
        summaries = run_verification_for_posts(post_ids, max_claims)
        logger.info(f"Verification task finished: {len(post_ids)} post(s), {len(summaries)} claim(s)")
        return {"post_ids": post_ids, "claims_processed": len(summaries), "summaries": summaries}


@celery_app.task(name="app.core.tasks.run_task_analysis", bind=True)
def run_task_analysis(self, task_id: int) -> Dict[str, Any]:
    """Run a profile analysis for an existing DB Task row."""

    flask_app = create_app()

    with flask_app.app_context():
        task = Task.query.get(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        # Install the owning user's BYOK keys + preferences for this run.
        from app.web.auth import load_user_context
        from app.utils.config import set_user_context, reset_user_context
        _ctx_token = set_user_context(load_user_context(task.user_id))
        start = time.time()
        try:
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.utcnow()
            task.progress = 5
            task.message = "Starting analysis..."
            db.session.commit()

            analyzer = SocialMediaAnalyzer()

            task.progress = 20
            task.message = "Running analyzer..."
            db.session.commit()

            result = analyzer.analyze_profile(task.platform, task.profile_id)

            task.progress = 90
            task.message = "Saving results..."
            db.session.commit()

            # Canonical: persist in DB; file is best-effort fallback
            try:
                task.result_data = json.loads(json.dumps(result, default=str))
                task.has_result = True
            except Exception as e:
                print(f"Failed to serialize result_data for task {task_id}: {e}")
                task.result_data = None
                task.has_result = False

            # Optional: best-effort file output (useful for local debugging)
            try:
                print(f"Attempting to save result to file for task {task_id}")
                task.result_path = _save_results_to_file(flask_app, task_id, result)
                print(f"Result saved to {task.result_path}")
            except Exception as e:
                print(f"Failed to save result file: {e}")
                task.result_path = None

            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.message = "Completed"
            task.completed_at = datetime.utcnow()
            task.duration = time.time() - start
            db.session.commit()

            return {"success": True, "task_id": task_id, "result_path": task.result_path}

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.message = "Failed"
            task.completed_at = datetime.utcnow()
            task.duration = time.time() - start
            db.session.commit()
            raise
        finally:
            reset_user_context(_ctx_token)
