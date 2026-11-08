"""
Database models for the web application
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import deferred
from datetime import datetime
import enum

# Initialize SQLAlchemy - will be initialized by the Flask app
db = SQLAlchemy()


class TaskStatus(enum.Enum):
    """Enum for task status values"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(db.Model):
    """Analysis task model"""

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    profile_id = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.PENDING)
    progress = db.Column(db.Integer, default=0)
    message = db.Column(db.String(255))
    result_path = db.Column(db.String(255))
    result_data = deferred(db.Column(db.JSON, nullable=True))
    has_result = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    error = db.Column(db.Text)
    duration = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    def __init__(self, platform: str, profile_id: str, status=None, **kwargs):
        """Initialize a new task"""
        self.platform = platform.lower()
        self.profile_id = profile_id
        # Accept status= for tests/fixtures; coerce str -> TaskStatus
        if status is not None:
            self.status = status if isinstance(status, TaskStatus) else TaskStatus(str(status).lower())
        else:
            self.status = TaskStatus.PENDING
        self.progress = kwargs.pop('progress', 0)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def start(self):
        """Mark task as started"""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self.message = "Analysis in progress..."
        db.session.commit()

    def update_progress(self, progress: int, message: str = None):
        """Update task progress"""
        self.progress = min(max(progress, 0), 100)
        if message:
            self.message = message
        db.session.commit()

    def complete(self, result_path: str = None, result_data=None):
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.progress = 100
        self.completed_at = datetime.utcnow()
        self.message = "Analysis completed successfully"

        if result_path:
            self.result_path = result_path

        if result_data is not None:
            self.result_data = result_data
            self.has_result = True

        if self.started_at:
            self.duration = (self.completed_at - self.started_at).total_seconds()

        db.session.commit()

    def fail(self, error: str):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.message = f"Analysis failed: {error}"
        self.completed_at = datetime.utcnow()

        if self.started_at:
            self.duration = (self.completed_at - self.started_at).total_seconds()

        db.session.commit()

    def to_dict(self):
        """Convert task to dictionary"""
        return {
            "id": self.id,
            "platform": self.platform,
            "profile_id": self.profile_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    def __repr__(self):
        return f"<Task {self.id}: {self.platform}/{self.profile_id} - {self.status}>"

# Import other models to ensure they are registered
from .dossier import DossierSnapshot, CrossPlatformProfile
from .verification import SocialMediaPost, Claim, VerificationResult, Platform, MediaType, LanguageCode, ClaimType, VerificationStatus
