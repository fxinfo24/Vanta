"""
View routes for the web interface
Handles page rendering and form submissions
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify,
)
import json
import os
from ..models import db, Task, TaskStatus
from sqlalchemy import desc
from datetime import datetime, timedelta

# Create the blueprint with a URL prefix - important for proper routing!
views_bp = Blueprint("views", __name__)


@views_bp.before_request
def redirect_ui_to_frontend():
    """Send browser traffic to the real UI when the host is API-only.

    On Render this origin serves the JSON API; the React app lives on Vercel and
    `app/web/static/dist` is not deployed, so the legacy Jinja pages here render
    unstyled. Setting `FRONTEND_URL` makes every non-API page a redirect instead
    of serving that broken shell. Unset locally, so `bin/run.py --web` keeps
    working as before.
    """
    frontend = (os.getenv("FRONTEND_URL") or "").rstrip("/")
    if not frontend or request.method != "GET" or request.path.startswith("/api"):
        return None
    suffix = "" if request.path == "/" else request.path
    if request.query_string:
        suffix += "?" + request.query_string.decode()
    return redirect(f"{frontend}{suffix}", code=302)


@views_bp.route("/")
def index():
    """Render homepage with analysis form"""
    # Get recent tasks
    recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
    return render_template("index.html", recent_tasks=recent_tasks)


@views_bp.route("/start-analysis", methods=["POST"])
def start_analysis():
    """Handle new analysis submission"""
    platform = request.form.get("platform")
    profile_id = request.form.get("profile_id")
    advanced = request.form.get("advanced_analysis") == "on"

    if not platform or not profile_id:
        flash("Please provide both platform and profile ID.", "danger")
        return redirect(url_for("views.index"))

    # Create new task
    task = Task(platform=platform, profile_id=profile_id)
    db.session.add(task)
    db.session.commit()

    # Return task ID for AJAX requests
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"task_id": task.id})

    # Redirect to task page for regular form submissions
    return redirect(url_for("views.task", task_id=task.id))


@views_bp.route("/tasks")
def tasks():
    """List all analysis tasks with filtering and pagination"""
    # Get filter parameters
    platform = request.args.get("platform")
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Build query
    query = Task.query

    if platform:
        query = query.filter_by(platform=platform.lower())
    if status:
        try:
            task_status = TaskStatus(status.lower())
            query = query.filter_by(status=task_status)
        except ValueError:
            flash(f"Invalid status filter: {status}", "warning")

    # Order by creation date, newest first
    query = query.order_by(desc(Task.created_at))

    # Paginate results
    tasks = query.paginate(page=page, per_page=per_page)

    return render_template("tasks.html", tasks=tasks, platform=platform, status=status)


@views_bp.route("/tasks/<int:task_id>")
def task(task_id):
    """Show details for a specific task"""
    task = Task.query.get_or_404(task_id)
    return render_template("task.html", task=task)


@views_bp.route("/result/<int:task_id>")
def result(task_id):
    """Show analysis results for a completed task"""
    task = Task.query.get_or_404(task_id)

    if task.status != TaskStatus.COMPLETED:
        flash("Results are only available for completed tasks.", "warning")
        return redirect(url_for("views.task", task_id=task_id))

    try:
        # Load results from the result path
        if task.result_path and os.path.exists(task.result_path):
            with open(task.result_path, "r") as f:
                results = json.load(f)
        else:
            # For testing: create mock results if file doesn't exist
            results = {
                "metadata": {
                    "profile_id": task.profile_id,
                    "platform": task.platform,
                    "analysis_date": datetime.now().isoformat(),
                },
                "content_analysis": {
                    "mock_data_disclaimer": "This is sample data for testing"
                },
                "authenticity_analysis": {
                    "overall_authenticity": {"score": 0.85, "confidence": 0.75}
                },
                "predictions": {},
            }

        # Render the template with both task and results data
        return render_template("result.html", task=task, results=results)
    except Exception as e:
        current_app.logger.error(f"Error displaying results for task {task_id}: {e}")
        flash("Error loading analysis results.", "danger")
        return redirect(url_for("views.task", task_id=task_id))


@views_bp.route("/dashboard")
def dashboard():
    """Show dashboard with analytics"""
    # Get task statistics
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status=TaskStatus.COMPLETED).count()
    failed_tasks = Task.query.filter_by(status=TaskStatus.FAILED).count()

    # Get platform distribution
    platform_stats = (
        db.session.query(Task.platform, db.func.count(Task.id))
        .group_by(Task.platform)
        .all()
    )

    # Get recent activity (last 10 tasks)
    recent_activity = Task.query.order_by(desc(Task.created_at)).limit(10).all()

    # Get average duration trend (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    duration_trend = (
        db.session.query(db.func.date(Task.created_at), db.func.avg(Task.duration))
        .filter(Task.status == TaskStatus.COMPLETED, Task.created_at >= seven_days_ago)
        .group_by(db.func.date(Task.created_at))
        .all()
    )

    return render_template(
        "dashboard.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        platform_stats=platform_stats,
        recent_activity=recent_activity,
        duration_trend=duration_trend,
    )
