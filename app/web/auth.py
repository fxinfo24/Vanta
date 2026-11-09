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
        return {"keys": {}, "preferred_model": None, "default_mode": "deep"}
    from .models.user import UserSettings
    from app.utils.config import decrypt_api_keys
    session = auth_session()
    try:
        row = session.query(UserSettings).filter_by(user_id=user_id).first()
        if row is None:
            return {"keys": {}, "preferred_model": None, "default_mode": "deep"}
        return {
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