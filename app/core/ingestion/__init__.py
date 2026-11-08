"""
Vanta: Ingestion Module
Data ingestion and validation for global verification pipeline
"""

from .schemas import ApifyFacebookPost, ApifyFacebookPostClean, PostSummary, MediaType
from .lang_detect import detect_language, batch_detect_languages
from .ingestor import ApifyIngestor, ingest_apify_dataset, ingest_from_json_file