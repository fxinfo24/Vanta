"""
Vanta: Utility Helper Functions
Common utility functions used across the application
"""

from datetime import datetime
import re
from typing import List, Optional
from urllib.parse import urlparse


def format_date(date_str: Optional[str], fmt: str = "%Y-%m-%d") -> str:
    """
    Format date string to specified format

    Args:
        date_str: Date string to format
        fmt: Output format (default: YYYY-MM-DD)

    Returns:
        Formatted date string
    """
    if not date_str:
        return ""

    try:
        # Try parsing common date formats
        for fmt_in in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                date_obj = datetime.strptime(date_str, fmt_in)
                return date_obj.strftime(fmt)
            except ValueError:
                continue
        return date_str  # Return original if parsing fails
    except Exception:
        return date_str


def extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text

    Args:
        text: Text to extract URLs from

    Returns:
        List of extracted URLs
    """
    # URL regex pattern
    url_pattern = (
        r"http[s]?://"  # http:// or https://
        r"(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|"  # allowed characters
        r"(?:%[0-9a-fA-F][0-9a-fA-F]))+"  # percent-encoded characters
    )

    # Find all URLs in text
    urls = re.findall(url_pattern, text)

    # Validate and clean URLs
    valid_urls = []
    for url in urls:
        try:
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                valid_urls.append(url)
        except Exception:
            continue

    return valid_urls


def clean_text(text: str) -> str:
    """
    Clean and normalize text

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = " ".join(text.split())

    # Remove control characters
    text = "".join(char for char in text if ord(char) >= 32 or char == "\n")

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove multiple consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def parse_timestamp(value) -> Optional[datetime]:
    """Parse the timestamps providers return (ISO 8601 with/without Z, epochs).

    Every metric below is computed from these, so one parser keeps the numbers
    agreeing wherever they are shown.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def engagement_rate_percent(followers, interactions, items) -> Optional[float]:
    """Mean interactions per post as a percentage of the follower base.

    `interactions` is the summed reactions+comments+shares over `items` posts.
    Returns None instead of a number when the denominator is missing: a rate
    computed without followers is not a small estimate, it is no estimate.
    """
    try:
        followers = float(followers)
        items = int(items)
        interactions = float(interactions)
    except (TypeError, ValueError):
        return None
    if followers <= 0 or items <= 0:
        return None
    return round(100.0 * (interactions / items) / followers, 3)


def posting_cadence(timestamps) -> dict:
    """Posts per day/week across the span the samples actually cover.

    Uses only parseable timestamps as the numerator: counting an undated post
    as published inside the window inflates the rate.
    """
    parsed = sorted(t for t in (parse_timestamp(v) for v in (timestamps or [])) if t)
    if len(parsed) < 2:
        return {"posts": len(parsed), "span_days": None,
                "posts_per_day": None, "posts_per_week": None}
    span_days = (parsed[-1] - parsed[0]).total_seconds() / 86400
    if span_days <= 0:
        return {"posts": len(parsed), "span_days": None,
                "posts_per_day": None, "posts_per_week": None}
    per_day = len(parsed) / span_days
    return {
        "posts": len(parsed),
        "span_days": round(span_days, 2),
        "posts_per_day": round(per_day, 3),
        "posts_per_week": round(per_day * 7, 2),
    }
