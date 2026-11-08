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


def create_app(test_config=None):
    """Create and configure the Flask application"""
    # Create Flask app instance
    app = Flask(
        __name__,
        static_url_path="/static",
        static_folder="static",
        template_folder="templates",
    )

    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "vanta.db")
    
    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-for-development-only"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URI", f"sqlite:///{db_path}"
        ),
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
            # In production, default to allowing Vercel frontends
            cors_origins = [
                "https://profile-scope.vercel.app",
                "https://profile-scope-git-main-fxinfo24s-projects.vercel.app",
                "http://localhost:5173",  # Vite dev server
                "http://127.0.0.1:5173",
            ]
            logger.info(f"Using default CORS origins: {cors_origins}")
    
    CORS(app, 
         resources={r"/api/*": {"origins": cors_origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

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
        # - In development/tests, `db.create_all()` is convenient.
        # - In production (Railway/Postgres), prefer Alembic migrations:
        #   `flask db upgrade`
        # Consolidated verification tables are created if missing so Product B
        # works without a separate migration flow:
        if app.config.get("TESTING"):
            db.create_all()
        else:
            try:
                db.create_all()
            except Exception as e:
                logger.warning(f"db.create_all() failed (migrations recommended in prod): {e}")

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
