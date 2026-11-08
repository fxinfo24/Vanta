"""
Vanta: Temporal & Contextual Verification (Layer 5)
Verify claims against timeline and context
"""

from .clients import GDELTClient, WaybackClient, NewsAPIClient, WikipediaClient
from .verifier import TemporalVerifier, verify_claim_temporally