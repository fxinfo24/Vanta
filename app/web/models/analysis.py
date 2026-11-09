"""
Vanta Analysis Models
Enhanced models for storing analysis results and tasks
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import json
from ..database import Base

class AnalysisStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Platform(enum.Enum):
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"

class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="analyses")
    
    # Analysis details
    platform = Column(Enum(Platform), nullable=False)
    profile_id = Column(String(255), nullable=False)  # Username or profile ID
    profile_display_name = Column(String(255), nullable=True)
    
    # Task status
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    progress = Column(Integer, default=0)  # 0-100 percentage
    message = Column(Text, nullable=True)  # Current processing message
    
    # Results storage
    profile_data = Column(JSON, nullable=True)  # Raw profile data
    analysis_results = Column(JSON, nullable=True)  # Processed analysis
    
    # Analysis metrics
    confidence_score = Column(Float, nullable=True)  # Overall confidence 0-1
    authenticity_score = Column(Float, nullable=True)  # Authenticity score 0-1
    influence_score = Column(Float, nullable=True)  # Influence score 0-1
    
    # Processing details
    processing_time = Column(Float, nullable=True)  # Processing time in seconds
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Analysis(id={self.id}, platform={self.platform}, profile={self.profile_id})>"
    
    def start_processing(self):
        """Mark analysis as started"""
        self.status = AnalysisStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self.progress = 0
    
    def update_progress(self, progress: int, message: str = None):
        """Update analysis progress"""
        self.progress = min(100, max(0, progress))
        if message:
            self.message = message
    
    def complete_analysis(self, results: dict, confidence: float = None, 
                         authenticity: float = None, influence: float = None):
        """Mark analysis as completed with results"""
        self.status = AnalysisStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100
        self.analysis_results = results
        
        if confidence is not None:
            self.confidence_score = confidence
        if authenticity is not None:
            self.authenticity_score = authenticity
        if influence is not None:
            self.influence_score = influence
            
        # Calculate processing time
        if self.started_at:
            self.processing_time = (self.completed_at - self.started_at).total_seconds()
    
    def fail_analysis(self, error: str):
        """Mark analysis as failed"""
        self.status = AnalysisStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
        self.progress = 0
    
    def get_results_summary(self):
        """Get summary of analysis results"""
        if not self.analysis_results:
            return None
            
        summary = {
            "profile_id": self.profile_id,
            "platform": self.platform.value,
            "status": self.status.value,
            "confidence": self.confidence_score,
            "authenticity": self.authenticity_score,
            "influence": self.influence_score,
            "processing_time": self.processing_time,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
        
        # Add key insights from results
        if self.analysis_results:
            results = self.analysis_results
            summary.update({
                "followers_count": results.get("profile_data", {}).get("followers_count", 0),
                "verified": results.get("profile_data", {}).get("verified", False),
                "sentiment": results.get("content_analysis", {}).get("sentiment", {}).get("overall"),
                "personality_traits": list(results.get("content_analysis", {}).get("personality_traits", {}).keys())[:3]
            })
            
        return summary

# Add relationship back to User model
from .user import User
User.analyses = relationship("Analysis", back_populates="user")