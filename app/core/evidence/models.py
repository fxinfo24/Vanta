"""
Vanta Evidence Models - Core data structures
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


class VerificationStatus(Enum):
    TRUE = "true"
    FALSE = "false"
    LIKELY_TRUE = "likely_true"
    MISLEADING = "misleading"
    DISPUTED = "disputed"
    UNVERIFIED = "unverified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"


class SourceType(Enum):
    OFFICIAL = "official"
    NEWS = "news"
    FACT_CHECK = "fact_check"
    SOCIAL = "social"
    ACADEMIC = "academic"
    GOVERNMENT = "government"
    ARCHIVE = "archive"


class ExtractionMethod(Enum):
    API = "api"
    SCRAPING = "scraping"
    OCR = "ocr"
    MANUAL = "manual"


@dataclass
class Claim:
    id: str
    text: str
    source_url: str = ""
    author: str = ""
    platform: str = ""
    language: str = "en"
    entities: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    id: str
    text: str
    source_url: str
    source_type: SourceType
    credibility_score: float = 0.5
    extraction_method: ExtractionMethod = ExtractionMethod.API
    language: str = "en"
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    claim_id: str
    status: VerificationStatus
    confidence_score: float
    evidence_used: List[str]
    reasoning: str
    contradictions: List[Dict[str, Any]]
    supporting_evidence: List[Dict[str, Any]]
    neutral_evidence: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)