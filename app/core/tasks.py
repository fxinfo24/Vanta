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
from typing import Any, Dict

from celery import Celery

from app.core.analyzer import SocialMediaAnalyzer
from app.web.app import create_app
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
    },
)


def _save_results_to_file(flask_app, task_id: int, result: Dict[str, Any]) -> str:
    results_dir = Path(flask_app.config["RESULTS_FOLDER"])
    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / f"{task_id}.json"

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    return str(result_path)


@celery_app.task(name="app.core.tasks.run_task_analysis", bind=True)
def run_task_analysis(self, task_id: int) -> Dict[str, Any]:
    """Run a profile analysis for an existing DB Task row."""

    flask_app = create_app()

    with flask_app.app_context():
        task = Task.query.get(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

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
