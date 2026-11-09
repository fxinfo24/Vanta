"""
Vanta User Model
Enhanced user management with authentication and subscriptions
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime
import enum
from ..database import Base

class UserRole(enum.Enum):
    USER = "user"
    PREMIUM = "premium" 
    ENTERPRISE = "enterprise"
    ADMIN = "admin"

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    EXPIRED = "expired"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    
    # User profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company = Column(String(200), nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    
    # Subscription
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    subscription_expires = Column(DateTime, nullable=True)
    
    # API usage tracking
    api_calls_count = Column(Integer, default=0)
    api_calls_limit = Column(Integer, default=100)  # Monthly limit
    api_calls_reset = Column(DateTime, default=func.now())
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)
    
    # API Key for programmatic access
    api_key = Column(String(64), unique=True, nullable=True)
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username or self.email
    
    def can_make_api_call(self):
        """Check if user can make API calls within their limit"""
        # Reset counter if month has passed
        now = datetime.utcnow()
        if self.api_calls_reset and (now - self.api_calls_reset).days >= 30:
            self.api_calls_count = 0
            self.api_calls_reset = now
            
        return self.api_calls_count < self.api_calls_limit
    
    def increment_api_calls(self):
        """Increment API call counter"""
        self.api_calls_count += 1
    
    def get_api_limits(self):
        """Get API limits based on subscription"""
        limits = {
            UserRole.USER: 100,
            UserRole.PREMIUM: 1000, 
            UserRole.ENTERPRISE: 10000,
            UserRole.ADMIN: 100000
        }
        return limits.get(self.role, 100)


class UserSettings(Base):
    """Per-user settings: analysis preferences + BYOK API keys.

    BYOK keys are stored ONLY as a Fernet-encrypted JSON blob
    (byok_keys_enc, {env_var: key}); plaintext never touches the DB and
    the API never returns key material (masked hints only). One row per
    user; created lazily on first save.
    """
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    default_mode = Column(String(20), default="deep")  # 'quick' | 'deep'
    preferred_model = Column(String(120), nullable=True)
    byok_keys_enc = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, mode={self.default_mode})>"


class PasswordResetToken(Base):
    """Single-use, expiring password reset token.

    Only a SHA-256 hash of the token is stored, so a database leak does not
    hand out working reset links. Rows are marked `used_at` on success instead
    of deleted, which keeps "this link was already used" distinguishable from
    "this link never existed".
    """
    __tablename__ = "password_reset_token"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<PasswordResetToken(user_id={self.user_id}, used={bool(self.used_at)})>"