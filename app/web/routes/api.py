# app/web/routes/api.py
"""
Vanta API Routes
Handles API endpoints for tasks and analysis results
"""
from flask import Blueprint, jsonify, request, current_app, send_file
from pathlib import Path
from datetime import datetime
import json
import threading
import os
import logging

from app.core.analyzer import SocialMediaAnalyzer
from ..models import db, Task, TaskStatus

logger = logging.getLogger("api")

# Initialize analyzer
analyzer = SocialMediaAnalyzer()

api_bp = Blueprint("api", __name__)


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


@api_bp.route("/analyze", methods=["POST"])
def start_analysis():
    """Start a new profile analysis task"""
    data = request.get_json()

    if not data or "platform" not in data or "profile_id" not in data:
        return (
            jsonify({"error": "Missing required fields: platform and profile_id"}),
            400,
        )

    # Create new task (Task.__init__ only accepts platform and profile_id)
    task = Task(
        platform=data["platform"].lower(),
        profile_id=data["profile_id"]
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
            mode = data.get("mode", "deep")
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
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict())


@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    """List all tasks with optional filtering"""
    # Get query parameters
    platform = request.args.get("platform")
    status = request.args.get("status")
    limit = request.args.get("limit", type=int, default=10)
    offset = request.args.get("offset", type=int, default=0)

    # Build query
    query = Task.query

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
    task = Task.query.get_or_404(task_id)
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
    task = Task.query.get_or_404(task_id)

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
    task = Task.query.get_or_404(task_id)

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


@api_bp.route("/tasks/<int:task_id>/results", methods=["GET"])
def get_results(task_id):
    """Get analysis results for a completed task"""
    task = Task.query.get_or_404(task_id)

    if task.status != TaskStatus.COMPLETED:
        msg = "Results only available for completed tasks"
        return jsonify({"error": msg}), 400

    # Canonical source: DB
    # Canonical source: DB - Only check if attribute exists (compatibility)
    if hasattr(task, 'result_data') and task.result_data is not None:
        return jsonify(task.result_data)

    # Backward-compatible fallback: file
    if task.result_path and Path(task.result_path).exists():
        try:
            with open(task.result_path, "r") as f:
                results = json.load(f)
            return jsonify(results)
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
    task = Task.query.get_or_404(task_id)
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
        .group_by(Task.platform)
        .all()
    )

    return jsonify(
        [{"platform": platform, "count": count} for platform, count in platform_stats]
    )


@api_bp.route("/stats/completion-rate", methods=["GET"])
def completion_rate():
    """Get task completion rate statistics"""
    total = Task.query.count()
    completed = Task.query.filter_by(status=TaskStatus.COMPLETED).count()
    failed = Task.query.filter_by(status=TaskStatus.FAILED).count()

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
    if not post:
        post = SocialMediaPost(
            id=post_id,
            platform=platform,
            profile_id=profile_id,
            text=text,
            content=text,
            text_hash=str(abs(hash(text)) % (2**32)),
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
    task = Task.query.get_or_404(task_id)
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
    posts = db.session.query(SocialMediaPost).order_by(SocialMediaPost.created_at.desc()).limit(limit).all()
    return jsonify({"posts": [_verification_payload(post=p) for p in posts], "total": len(posts)})


@api_bp.route("/verification/claims", methods=["GET"])
def list_verification_claims():
    from app.web.models.verification import Claim
    limit = request.args.get("limit", type=int, default=20)
    claims = db.session.query(Claim).order_by(Claim.extracted_at.desc()).limit(limit).all()
    return jsonify({"claims": [_verification_payload(claim=c)["claim"] for c in claims], "total": len(claims)})


@api_bp.route("/verification/claim/<claim_id>", methods=["GET"])
def get_verification_claim(claim_id):
    from app.web.models.verification import Claim, VerificationResult
    claim = db.session.query(Claim).filter_by(id=claim_id).first()
    if not claim:
        return jsonify({"error": "Claim not found"}), 404
    vr = db.session.query(VerificationResult).filter_by(claim_id=claim.id).first()
    return jsonify(_verification_payload(claim=claim, vr=vr))


@api_bp.route("/verification/results", methods=["GET"])
def list_verification_results():
    from app.web.models.verification import VerificationResult
    limit = request.args.get("limit", type=int, default=20)
    rows = db.session.query(VerificationResult).order_by(VerificationResult.created_at.desc()).limit(limit).all()
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
        post = db.session.query(SocialMediaPost).filter_by(id=data["post_id"]).first()
        if not post:
            return jsonify({"error": "Post not found"}), 404
        claims = extractor.extract_claims_from_post(post)
        summaries.append({"stage": "extract", "post_id": post.id, "claims": len(claims)})
    else:
        processed, extracted = extractor.process_unprocessed_posts(limit=limit)
        summaries.append({"stage": "extract", "processed_posts": processed, "claims_extracted": extracted})
    # 2-4) Fact-check -> temporal -> RAG -> confidence for claims lacking verification
    from app.web.models.verification import VerificationResult
    claims = db.session.query(Claim).limit(limit).all()
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
    post = db.session.query(SocialMediaPost).filter_by(id=post_id).first()
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
