"""
Vanta Authentication System
JWT-based authentication with role-based access control
"""

import os
import jwt
import bcrypt
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

from .models.user import User, UserRole

logger = logging.getLogger("auth")

# Load environment variables
load_dotenv()

# JWT Configuration: prefer a dedicated secret, fall back to the Flask
# SECRET_KEY (present in .env). Never ship a hardcoded production secret.
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "dev-jwt-key-change-in-production"
    logger.warning("JWT_SECRET_KEY/SECRET_KEY not set; using insecure dev key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

class AuthenticationError(Exception):
    """Authentication related errors"""
    pass

class AuthorizationError(Exception):
    """Authorization related errors"""
    pass

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        # PyJWT 2.x: InvalidTokenError is the base class of every decode
        # failure (bad signature, malformed token, wrong algorithm, ...).
        raise AuthenticationError("Invalid token")

def authenticate_user(email: str, password: str, db: Session) -> Optional[User]:
    """Authenticate a user with email and password"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return None
        
    if not verify_password(password, user.hashed_password):
        return None
        
    if not user.is_active:
        return None
        
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user

def create_user(email: str, password: str, username: str = None, 
                first_name: str = None, last_name: str = None,
                db: Session = None) -> User:
    """Create a new user"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise AuthenticationError("User with this email already exists")
    
    if username:
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise AuthenticationError("Username already taken")
    
    # Create new user
    hashed_pw = hash_password(password)
    
    user = User(
        email=email,
        username=username,
        hashed_password=hashed_pw,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.USER  # Default role
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

def auth_session() -> Session:
    """Session bound to the *Flask app's* engine.

    `User` lives on the legacy declarative `Base` (database.py, used by the
    enterprise modules), but its table is created in whichever database the
    Flask app is configured with (app.py does User.__table__.create on the
    app engine). Binding sessions to that engine keeps tests (in-memory DB)
    and production on the same store instead of the module-level engine in
    database.py, which would silently point tests at the live DB file.
    """
    from .models import db as flask_db
    # Inside an app context, flask_db.engine is the app's engine.
    return sessionmaker(bind=flask_db.engine)()


def user_to_dict(user: User) -> Dict[str, Any]:
    """Public representation of a user (never includes the password hash)."""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": bool(user.is_active),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def token_required(func):
    """Flask decorator: require `Authorization: Bearer <jwt>`.

    Sets flask.g.current_user on success; returns a JSON 401 otherwise.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from flask import request, g, jsonify
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Authentication required (Bearer token)"}), 401
        session = auth_session()
        try:
            g.current_user = get_current_user(header[len("Bearer "):].strip(), session)
        except AuthenticationError as e:
            return jsonify({"error": str(e)}), 401
        finally:
            session.close()
        return func(*args, **kwargs)
    return wrapper


def get_current_user(token: str, db: Session) -> User:
    """Get current user from JWT token"""
    try:
        payload = verify_token(token)
        user_id: int = payload.get("sub")
        
        if user_id is None:
            raise AuthenticationError("Invalid token payload")
            
    except AuthenticationError:
        raise
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AuthenticationError("User not found")
        
    return user

def require_role(required_role: UserRole):
    """Decorator to require specific user role"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract user from kwargs (assumes user is passed)
            user = kwargs.get('current_user')
            if not user:
                raise AuthorizationError("Authentication required")
            
            # Check role hierarchy
            role_hierarchy = {
                UserRole.USER: 0,
                UserRole.PREMIUM: 1,
                UserRole.ENTERPRISE: 2,
                UserRole.ADMIN: 3
            }
            
            user_level = role_hierarchy.get(user.role, 0)
            required_level = role_hierarchy.get(required_role, 0)
            
            if user_level < required_level:
                raise AuthorizationError(f"Role {required_role.value} required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_or_create_settings(db: Session, user_id: int) -> "UserSettings":
    """Fetch the UserSettings row for a user, creating an empty one lazily."""
    from .models.user import UserSettings
    settings = db.query(UserSettings).filter_by(user_id=user_id).first()
    if settings is None:
        settings = UserSettings(user_id=user_id, default_mode="deep")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def load_user_context(user_id: Optional[int]) -> Dict[str, Any]:
    """Execution context for one user's analysis runs.

    Returns {"keys": {env_var: plaintext_key}, "preferred_model": str|None,
    "default_mode": str}. Keys are decrypted from the user's encrypted
    BYOK blob. A user with no settings (or legacy task with user_id NULL)
    gets an empty key dict - clients then fall back to server env vars.
    """
    if user_id is None:
        return {"user_id": None, "keys": {}, "preferred_model": None, "default_mode": "deep"}
    from .models.user import UserSettings
    from app.utils.config import decrypt_api_keys
    session = auth_session()
    try:
        row = session.query(UserSettings).filter_by(user_id=user_id).first()
        if row is None:
            return {"user_id": user_id, "keys": {}, "preferred_model": None, "default_mode": "deep"}
        return {
            "user_id": user_id,
            "keys": decrypt_api_keys(row.byok_keys_enc),
            "preferred_model": row.preferred_model,
            "default_mode": row.default_mode or "deep",
        }
    finally:
        session.close()


def generate_api_key() -> str:
    """Generate a new API key"""
    import secrets
    return f"psk_{secrets.token_urlsafe(32)}"

def create_user_with_api_key(email: str, password: str, db: Session) -> tuple[User, str]:
    """Create user and generate API key"""
    user = create_user(email, password, db=db)
    api_key = generate_api_key()
    
    user.api_key = api_key
    db.commit()
    
    return user, api_key

def authenticate_api_key(api_key: str, db: Session) -> Optional[User]:
    """Authenticate using API key"""
    user = db.query(User).filter(User.api_key == api_key).first()
    
    if not user or not user.is_active:
        return None
        
    return user


# ---------------------------------------------------------------------------
# Password reset (one-time emailed tokens)
# ---------------------------------------------------------------------------
# The link carries a random token; the database stores only its SHA-256 hash.
# Tokens expire (RESET_TOKEN_TTL_MINUTES, default 30), are single use, and
# issuing a new one retires every unused token for that user.

RESET_TOKEN_TTL_MINUTES = int(os.getenv("RESET_TOKEN_TTL_MINUTES", "30") or "30")
RESET_MAX_REQUESTS_PER_HOUR = int(os.getenv("RESET_MAX_REQUESTS_PER_HOUR", "3") or "3")


class EmailNotConfigured(Exception):
    """No transactional email provider is configured on this deployment."""


class EmailDeliveryError(Exception):
    """The provider was configured but the message could not be sent."""


def _hash_reset_token(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_reset_token(db: Session, user: User) -> str:
    """Create a reset token for `user`, retiring any unused earlier ones."""
    import secrets
    from .models.user import PasswordResetToken

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: datetime.utcnow()}, synchronize_session=False)

    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw),
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    ))
    db.commit()
    return raw


def revoke_reset_token(db: Session, raw: str) -> None:
    """Drop a token whose email never went out.

    Without this, a failed send still counted against the per-hour request
    limit and left a usable-looking row in the table.
    """
    from .models.user import PasswordResetToken
    db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == _hash_reset_token(raw)
    ).delete(synchronize_session=False)
    db.commit()


def recent_reset_requests(db: Session, user_id: int) -> int:
    """How many reset tokens were issued for this user in the last hour."""
    from .models.user import PasswordResetToken
    since = datetime.utcnow() - timedelta(hours=1)
    return db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.created_at >= since,
    ).count()


def consume_reset_token(db: Session, raw: str) -> Optional[User]:
    """Redeem a reset token. Returns the user, or None if invalid/expired/used."""
    from .models.user import PasswordResetToken

    if not raw:
        return None
    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == _hash_reset_token(raw)
    ).first()
    if row is None or row.used_at is not None:
        return None
    if row.expires_at is not None and row.expires_at < datetime.utcnow():
        return None
    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None or not user.is_active:
        return None
    row.used_at = datetime.utcnow()
    # Any other outstanding link for this account stops working with the reset.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return user


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """Send the reset link through Resend or Brevo (whichever is configured).

    Raises EmailNotConfigured when neither key exists - the API turns that into
    an explicit 503 rather than pretending an email went out.
    """
    import requests

    sender = os.getenv("RESET_FROM_EMAIL") or "Vanta <onboarding@resend.dev>"
    subject = "Reset your Vanta password"
    text_body = (
        "Use the link below to set a new password. It expires in "
        f"{RESET_TOKEN_TTL_MINUTES} minutes and can be used once.\n\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    resend_key = os.getenv("RESEND_API_KEY")
    brevo_key = os.getenv("BREVO_API_KEY")

    if resend_key:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}"},
            json={"from": sender, "to": [to_email], "subject": subject, "text": text_body},
            timeout=15,
        )
        if resp.status_code >= 400:
            raise EmailDeliveryError(f"Resend {resp.status_code}: {resp.text[:200]}")
        return

    if brevo_key:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={
                "sender": {"email": sender.split("<")[-1].rstrip(">"), "name": "Vanta"},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": text_body,
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            raise EmailDeliveryError(f"Brevo {resp.status_code}: {resp.text[:200]}")
        return

    raise EmailNotConfigured(
        "No email provider configured. Set RESEND_API_KEY (or BREVO_API_KEY) and "
        "RESET_FROM_EMAIL on this service to enable emailed reset links."
    )