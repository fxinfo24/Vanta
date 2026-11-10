"""
Vanta Web Application
Flask web interface for the Vanta analyzer
"""

import os
import logging
from flask import Flask
from flask_migrate import Migrate
from flask_cors import CORS

# Setup logging - production-safe (logs to stdout if logs/ doesn't exist)
log_file = None
logs_dir = os.path.join(os.getcwd(), "logs")
if os.path.exists(logs_dir) or os.access(os.getcwd(), os.W_OK):
    try:
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "vanta_web.log")
    except (OSError, PermissionError):
        # If we can't create logs directory, log to stdout
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file,  # None means log to stdout
)
logger = logging.getLogger("Vanta.Web")

# Import db from models (shared SQLAlchemy instance)
from app.web.models import db
from app.utils.config import database_uri
from dotenv import load_dotenv


def create_app(test_config=None):
    """Create and configure the Flask application"""
    # Load .env before reading any environment variable. Without this, a process
    # that imported the factory before dotenv ran saw DATABASE_URI unset and
    # silently used SQLite - two processes then served different databases.
    load_dotenv()

    # Create Flask app instance
    app = Flask(
        __name__,
        static_url_path="/static",
        static_folder="static",
        template_folder="templates",
    )

    # Create data directory if it doesn't exist
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "vanta.db")

    # URI normalisation (relative SQLite anchor, postgres alias, driver, SSL) is
    # shared with app/web/database.py so the two engines cannot drift apart.

    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-for-development-only"),
        SQLALCHEMY_DATABASE_URI=database_uri(f"sqlite:///{db_path}"),
        # A pooled Postgres endpoint drops idle connections; without pre-ping the
        # first query after a quiet spell fails with a dead-connection error.
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        RESULTS_FOLDER=os.path.join(os.getcwd(), "data", "results"),
    )

    # Override default configuration
    if test_config:
        app.config.update(test_config)

    # Ensure instance folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["RESULTS_FOLDER"], exist_ok=True)

    # Initialize extensions with app
    db.init_app(app)
    Migrate(app, db)
    
    # Configure CORS
    cors_origins = os.environ.get("CORS_ORIGINS", "").split(",")
    # Filter out empty strings and strip whitespace
    cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]
    
    # If no origins specified, use smart defaults
    if not cors_origins:
        if app.config.get("DEBUG") or os.environ.get("FLASK_ENV") == "development":
            cors_origins = ["*"]
        else:
            # In production, default to allowing the Vercel frontend. The old
            # defaults pointed at retired profile-scope hosts, so an unset
            # CORS_ORIGINS would have blocked every request from the live site.
            cors_origins = [
                "https://vanta-intel.vercel.app",
                "http://localhost:5173",  # Vite dev server
                "http://127.0.0.1:5173",
            ]
            logger.info(f"Using default CORS origins: {cors_origins}")
    
    CORS(app, 
         resources={r"/api/*": {"origins": cors_origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

    # Baseline response headers for the API origin itself (Vercel covers the
    # frontend). setdefault keeps anything a route already chose - including the
    # CORS headers that flask-cors adds on the same response.
    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response

    with app.app_context():
        # Import and register blueprints
        from .routes.api import api_bp
        from .routes.views import views_bp

        app.register_blueprint(api_bp, url_prefix="/api")
        app.register_blueprint(views_bp)

        # Import and register error handlers
        from .error_handlers import register_handlers

        register_handlers(app)

        # Import and register filters
        from .filters import register_filters

        register_filters(app)

        # Database schema management
        # - SQLite / tests: `db.create_all()` is convenient.
        # - Postgres: Alembic owns the schema (`flask db upgrade`). Calling
        #   create_all() there made every migration fail with "type taskstatus
        #   already exists", because the app had already built the tables and
        #   left alembic_version empty.
        _db_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        if app.config.get("TESTING") or _db_uri.startswith("sqlite"):
            db.create_all()
        else:
            logger.info("Schema is managed by migrations; run `flask db upgrade` after deploying")
        # User lives on the legacy declarative Base (enterprise modules use
        # it); create its table in the app's database so auth works in both
        # production and tests (in-memory DB).
        try:
            from .models.user import (
                User as _User,
                UserSettings as _UserSettings,
                PasswordResetToken as _PasswordResetToken,
            )
            _User.__table__.create(bind=db.engine, checkfirst=True)
            _UserSettings.__table__.create(bind=db.engine, checkfirst=True)
            # Created after `users`: the reset tokens carry a foreign key to it.
            _PasswordResetToken.__table__.create(bind=db.engine, checkfirst=True)
        except Exception as e:
            logger.warning(f"users/user_settings/password_reset_token table creation failed: {e}")

    return app


def main():
    """Run the application"""
    app = create_app()

    # Get configuration from environment or use defaults
    host = os.environ.get("FLASK_HOST", "localhost")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
