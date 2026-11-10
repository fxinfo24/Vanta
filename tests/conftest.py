"""
Common pytest configuration and fixtures
"""

import os
import sys
import pytest
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Add the parent directory to sys.path to allow importing app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Add the project root directory to the path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Set up logging for tests
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create test directories if they don't exist
os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)


# Run cleanup script before pytest session starts
def pytest_configure(config):
    """Configure pytest and run cleanup script"""
    # Configure metadata
    config._metadata = {
        "Project": "Vanta",
        "Version": "1.0.0",
        "Python": sys.version,
        "Platform": sys.platform,
        "Test Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Run cleanup script before starting tests, only if not already run
    # (prevents duplicate cleanup when using run_tests.py)
    if os.environ.get("PROFILESCOPE_CLEANUP_RUN") != "1":
        cleanup_script = ROOT_DIR / "scripts" / "cleanup.sh"

        if cleanup_script.exists():
            print("\n=== Running Cleanup Script ===\n")
            try:
                result = subprocess.run(
                    ["bash", str(cleanup_script)], capture_output=True, text=True
                )

                if result.returncode == 0:
                    print("✅ Cleanup completed successfully")
                    # Mark cleanup as run to avoid duplicate execution
                    os.environ["PROFILESCOPE_CLEANUP_RUN"] = "1"
                else:
                    print(
                        f"⚠️ Cleanup script returned non-zero exit code: {result.returncode}"
                    )
                    if result.stderr:
                        print(f"Error output: {result.stderr}")
            except Exception as e:
                print(f"⚠️ Failed to run cleanup script: {e}")
        else:
            print(f"⚠️ Cleanup script not found at: {cleanup_script}")


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory path"""
    return ROOT_DIR


@pytest.fixture(scope="session")
def test_data_dir():
    """Return the test data directory path"""
    data_dir = ROOT_DIR / "tests" / "test_data"
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def sample_config_file(test_data_dir):
    """Create and return a sample config file for testing"""
    config_file = test_data_dir / "test_config.json"
    test_config = {
        "rate_limits": {"twitter": 50, "facebook": 50},
        "analysis": {
            "nlp_model": "test_model",
            "sentiment_analysis": True,
            "confidence_threshold": 0.5,
        },
        "output": {"save_raw_data": True, "export_format": "json"},
        "logging": {"level": "DEBUG", "file": "test.log"},
    }

    with open(config_file, "w") as f:
        import json

        json.dump(test_config, f, indent=2)

    return config_file


@pytest.fixture
def test_config():
    """Create test configuration"""
    return {
        "rate_limits": {"twitter": 50, "facebook": 50},
        "analysis": {
            "nlp_model": "test_model",
            "sentiment_analysis": True,
            "confidence_threshold": 0.5,
            "use_mock_data": True,
        },
        "output": {"save_raw_data": True, "export_format": "json"},
        "logging": {"level": "DEBUG", "file": "test_analyzer.log"},
    }


@pytest.fixture
def mock_profile_data():
    """Create mock profile data for testing"""
    return {
        "profile": {
            "username": "test_user",
            "bio": "This is a test bio for content analyzer tests.",
            "join_date": "2021-01-01",
            "location": "Test City",
            "followers_count": 100,
            "following_count": 50,
        },
        "posts": [
            {
                "id": f"post{i}",
                "content": f"This is test post #{i}.",
                "date": f"2021-02-{i+1:02d}T12:00:00Z",
                "likes": i * 10,
                "shares": i * 2,
            }
            for i in range(5)  # Reduce number of posts for quicker tests
        ],
    }


@pytest.fixture
def app():
    """Create test Flask app"""
    try:
        from app.web.app import create_app

        # Create app with testing config
        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "PRESERVE_CONTEXT_ON_EXCEPTION": False,
                # Never inherit this machine's recorded provider balance: a low
                # local balance must not fail unrelated route tests.
                "PROVIDER_USAGE_PATH": "/nonexistent/vanta_provider_usage.json",
            }
        )

        # Create application context
        with app.app_context():
            try:
                from app.web.models import db

                db.create_all()
            except Exception as e:
                print(f"Warning: Could not create database tables: {e}")

            # Provide the app
            yield app

            # Clean up
            try:
                from app.web.models import db

                db.drop_all()
            except Exception as e:
                print(f"Warning: Could not drop database tables: {e}")
    except ImportError as e:
        pytest.skip(f"Could not import Flask app: {e}")
    except Exception as e:
        pytest.skip(f"Error setting up Flask app: {e}")


@pytest.fixture(autouse=True)
def _no_local_dossier_cache():
    """Keep analyzer runs outside a fixture app context off the real database.

    CLI/desktop runs fall back to the local `data/vanta.db` for their dossier
    cache. A unit test that calls `analyze_profile` without the `app` fixture
    would otherwise read - and write - the developer's actual database, which
    makes test results depend on what the last local run collected. Tests that
    exercise the cache install their own app explicitly.
    """
    import app.core.analyzer as analyzer_module

    saved = (analyzer_module._CACHE_APP, analyzer_module._CACHE_APP_FAILED)
    analyzer_module._CACHE_APP, analyzer_module._CACHE_APP_FAILED = None, True
    try:
        yield
    finally:
        analyzer_module._CACHE_APP, analyzer_module._CACHE_APP_FAILED = saved


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


# Optional pytest-html integration
#
# Root cause of prior failures:
# - These functions implement hooks that only exist when the `pytest-html` plugin
#   is installed and *loaded*.
# - If pytest-html is not loaded (common in minimal envs, or when plugin autoload
#   is disabled for determinism), pytest treats these as unknown hooks and aborts
#   collection with a PluginValidationError.
#
# Fix:
# - Only register these hook implementations when pytest-html is present.

def pytest_configure(config):
    """Register optional plugins/hooks."""
    if config.pluginmanager.hasplugin("html"):
        config.pluginmanager.register(_VantaPytestHtmlHooks(), "vanta-pytest-html-hooks")


class _VantaPytestHtmlHooks:
    def pytest_html_report_title(self, report):
        """Set the title for the HTML report"""
        report.title = "Vanta Test Report"

    def pytest_html_results_summary(self, prefix, summary, postfix):
        """Add custom summary information to the HTML report"""
        prefix.extend(
            [
                "<p>Vanta test results. Failures must be addressed before deployment.</p>",
            ]
        )


# Completely rewritten pytest_runtest_makereport hook to fix the KeyError: 'content' issue
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Customize test result report data"""
    outcome = yield
    report = outcome.get_result()

    # Initialize extra if it doesn't exist
    if not hasattr(report, "extra"):
        report.extra = []

    # Only add details for test calls (not setup/teardown)
    if report.when == "call":
        # Add basic test metadata as format/value pairs
        report.extra.append(
            {"name": "Module", "value": item.module.__name__, "format": "text"}
        )

        if hasattr(item, "cls") and item.cls:
            report.extra.append(
                {"name": "Class", "value": item.cls.__name__, "format": "text"}
            )

        # Add function name
        report.extra.append({"name": "Function", "value": item.name, "format": "text"})

        # For failed tests, add error details - ensure content field exists
        if report.failed and hasattr(report, "longrepr"):
            report.extra.append(
                {
                    "name": "Error Details",
                    "value": str(report.longrepr),
                    "format": "text",
                    "content": str(
                        report.longrepr
                    ),  # Add content field to prevent KeyError
                }
            )
