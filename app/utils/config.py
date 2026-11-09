"""
Vanta: Configuration Utilities
Handles loading and validation of configuration settings
"""

import os
import json
import logging
import base64
import hashlib
import contextvars
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger("Vanta.Config")


# ---------------------------------------------------------------------------
# Per-user execution context + BYOK (bring your own key) resolution
# ---------------------------------------------------------------------------
# API-layer entry points (Flask before_request for sync routes, the
# analysis background thread, and the Celery worker) install the owning
# user's resolved keys + preferences into this ContextVar before running
# any client code. Client modules resolve keys via resolve_api_key()
# (user key -> server env fallback), so a user's own keys are used for
# THEIR analyses only and a missing key never falls back to mock data.

BYOK_PROVIDERS: Dict[str, Dict[str, str]] = {
    "openrouter": {"label": "OpenRouter (LLM)", "env_var": "OPENROUTER_API_KEY"},
    "scrapecreators": {"label": "ScrapeCreators (data)", "env_var": "SCRAPECREATORS_API_KEY"},
    "newsapi": {"label": "NewsAPI (temporal verification)", "env_var": "NEWSAPI_KEY"},
    "google_factcheck": {"label": "Google Fact Check", "env_var": "GOOGLE_FACT_CHECK_API_KEY"},
    "claimbuster": {"label": "ClaimBuster (check-worthiness)", "env_var": "CLAIMBUSTER_API_KEY"},
    "apify": {"label": "Apify (fallback scraper)", "env_var": "APIFY_API_TOKEN"},
}

# env_var -> provider key, for status reporting
_BYOK_ENV_TO_PROVIDER = {v["env_var"]: k for k, v in BYOK_PROVIDERS.items()}

DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

_user_context_var: contextvars.ContextVar = contextvars.ContextVar(
    "vanta_user_context", default=None
)


def set_user_context(ctx: Optional[Dict[str, Any]]):
    """Install the execution context for the current thread/async context.
    Returns an opaque token for reset_user_context()."""
    return _user_context_var.set(ctx)


def reset_user_context(token) -> None:
    if token is not None:
        _user_context_var.reset(token)


def get_user_context() -> Optional[Dict[str, Any]]:
    return _user_context_var.get()


def resolve_api_key(env_var: str) -> Optional[str]:
    """Resolve an API key: the owning user's BYOK key first, then the
    server environment variable. Returns None when neither is set."""
    ctx = _user_context_var.get()
    if ctx:
        key = (ctx.get("keys") or {}).get(env_var)
        if key:
            return key
    return os.getenv(env_var)


def resolve_openrouter_model() -> str:
    """User's preferred OpenRouter model -> OPENROUTER_MODEL env -> default."""
    ctx = _user_context_var.get()
    if ctx and ctx.get("preferred_model"):
        return ctx["preferred_model"]
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)


def key_source(env_var: str) -> str:
    """'user' when the key comes from BYOK, 'server' when from env,
    'none' when unset. Used for status reporting (never exposes values)."""
    ctx = _user_context_var.get()
    if ctx and (ctx.get("keys") or {}).get(env_var):
        return "user"
    return "server" if os.getenv(env_var) else "none"


def mask_key(key: Optional[str]) -> str:
    """Display hint for a stored key: bullet prefix + last 4 chars."""
    if not key:
        return ""
    return f"\u2022\u2022\u2022\u2022{key[-4:]}" if len(key) >= 4 else "\u2022\u2022\u2022\u2022"


# --- BYOK storage encryption (Fernet, key derived from server secret) ----

def _fernet():
    from cryptography.fernet import Fernet
    load_dotenv(override=True)
    secret = os.getenv("BYOK_ENCRYPTION_KEY") or os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "BYOK_ENCRYPTION_KEY or SECRET_KEY must be set to store API keys"
        )
    digest = hashlib.sha256((secret + "::vanta-byok-v1").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_keys(keys: Dict[str, str]) -> str:
    """Encrypt a {env_var: key} dict for storage. Plaintext never persisted."""
    return _fernet().encrypt(json.dumps(keys, sort_keys=True).encode()).decode()


def decrypt_api_keys(encrypted: Optional[str]) -> Dict[str, str]:
    """Decrypt a stored BYOK blob. Returns {} for empty/corrupt data;
    decryption failure means the server secret rotated - the user must
    re-enter their keys (never crashes the pipeline, never guesses)."""
    if not encrypted:
        return {}
    try:
        return json.loads(_fernet().decrypt(encrypted.encode()).decode())
    except Exception as e:
        logger.error(f"BYOK decryption failed (secret rotated?): {e}")
        return {}


class ConfigError(Exception):
    """Configuration related errors"""

    pass


class ConfigValidator:
    """Configuration validation helper"""

    @staticmethod
    def validate_api_keys(config: Dict[str, Any]) -> None:
        """
        Validate API configuration sections
        Args:
            config: Configuration dictionary
        Raises:
            ConfigError: If validation fails
        """
        if "api" not in config:
            raise ConfigError("Missing 'api' section in configuration")

        # Validate Twitter config
        twitter_config = config["api"].get("twitter", {})
        if any(twitter_config.values()):  # Only validate if any keys are set
            required_twitter = [
                "api_key",
                "api_secret",
                "access_token",
                "access_token_secret",
            ]
            missing = [key for key in required_twitter if not twitter_config.get(key)]
            if missing:
                raise ConfigError(
                    f"Missing Twitter API credentials: {', '.join(missing)}"
                )

        # Validate Facebook config
        facebook_config = config["api"].get("facebook", {})
        if any(facebook_config.values()):  # Only validate if any keys are set
            required_facebook = ["app_id", "app_secret", "access_token"]
            missing = [key for key in required_facebook if not facebook_config.get(key)]
            if missing:
                raise ConfigError(
                    f"Missing Facebook API credentials: {', '.join(missing)}"
                )


def get_config_path() -> Path:
    """
    Get the configuration file path
    Returns:
        Path to configuration file
    """
    # Check environment variable first
    env_path = os.getenv("PROFILESCOPE_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        logger.warning(
            f"Config file specified in PROFILESCOPE_CONFIG not found: {env_path}"
        )

    # Check common locations. config/config.json is the documented location, so
    # it is looked up both relative to the cwd and to the project root: without
    # those entries the file was never read and every "config" default silently
    # came from this module instead.
    project_root = Path(__file__).resolve().parents[2]
    common_locations = [
        Path("config/config.json"),
        project_root / "config" / "config.json",
        Path("config.json"),  # Current directory
        Path("../config.json"),  # Parent directory
        Path.home() / ".vanta/config.json",  # User home directory
        Path("/etc/vanta/config.json"),  # System-wide configuration
    ]

    for path in common_locations:
        if path.exists():
            return path

    return Path("config.json")  # Default to current directory


SPECIAL_CATEGORY_ENV = "ALLOW_SPECIAL_CATEGORY_INFERENCE"


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def allows_special_category_inference() -> bool:
    """Whether this deployment may infer Art. 9 categories about a subject.

    Political opinions, intimate-relationship patterns and substance use are
    inferred about people who never agreed to be analysed, so the default is
    **off** and has to be switched on deliberately - env var first, then
    config.json. Anything other than an explicit yes stays closed.
    """
    env = os.getenv(SPECIAL_CATEGORY_ENV)
    if env is not None and str(env).strip():
        return _truthy(env)
    try:
        cfg = load_config()
    except Exception as e:  # unreadable config must fail closed, not open
        logger.warning(f"Could not read privacy config ({e}); special-category inference stays disabled")
        return False
    return _truthy((cfg.get("privacy") or {}).get("allow_special_category_inference", False))


def retention_days() -> Dict[str, int]:
    """Retention windows for stored analysis data, in days."""
    defaults = {"raw_content_days": 30, "quote_receipt_days": 90, "snapshot_days": 365}
    try:
        cfg = load_config()
    except Exception as e:
        logger.warning(f"Could not read retention config ({e}); using defaults")
        return defaults
    configured = (cfg.get("privacy") or {}).get("retention") or {}
    out = {}
    for key, default in defaults.items():
        try:
            value = int(os.getenv(key.upper(), configured.get(key, default)))
        except (TypeError, ValueError):
            value = default
        out[key] = max(value, 1)
    return out


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json and environment variables
    Returns:
        Dictionary containing merged configuration
    Raises:
        ConfigError: If configuration loading or validation fails
    """
    # Load .env file if it exists
    load_dotenv()

    config_path = get_config_path()

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.warning(
            f"Config file not found at {config_path}, using empty configuration"
        )
        config = {}
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {str(e)}")
    except Exception as e:
        raise ConfigError(f"Failed to load config file: {str(e)}")

    # Initialize API sections if not present
    config.setdefault("api", {})
    config["api"].setdefault("twitter", {})
    config["api"].setdefault("facebook", {})

    # Twitter credentials from environment
    env_twitter = {
        "api_key": os.getenv("TWITTER_API_KEY"),
        "api_secret": os.getenv("TWITTER_API_SECRET"),
        "access_token": os.getenv("TWITTER_ACCESS_TOKEN"),
        "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    }

    # Facebook credentials from environment
    env_facebook = {
        "app_id": os.getenv("FACEBOOK_APP_ID"),
        "app_secret": os.getenv("FACEBOOK_APP_SECRET"),
        "access_token": os.getenv("FACEBOOK_ACCESS_TOKEN"),
    }

    # Update config with environment variables (only if they exist)
    for key, value in env_twitter.items():
        if value:
            config["api"]["twitter"][key] = value

    for key, value in env_facebook.items():
        if value:
            config["api"]["facebook"][key] = value

    try:
        # Validate configuration
        ConfigValidator.validate_api_keys(config)
        return config
    except ConfigError as e:
        logger.warning(f"Configuration validation warning: {str(e)}")
        return config  # Return config even if validation fails
