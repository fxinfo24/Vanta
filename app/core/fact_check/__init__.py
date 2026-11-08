"""
Vanta: Fact-Check API Integration (Layer 4)
Connect claims to external fact-check databases
"""

from .clients import GoogleFactCheckClient, FullFactClient, FactCheckClient
from .matcher import FactCheckMatcher, match_claim_to_fact_checks