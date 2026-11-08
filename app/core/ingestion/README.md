# Vanta Ingestion Module

Global social media data ingestion pipeline for verification system.

## Overview

This module provides:

1. **Schema validation** (Layer 1) using Pydantic for Apify Facebook data
2. **Language detection** (EN + BN + 176 languages via fasttext)
3. **Database models** (PostgreSQL/SQLite) for storing posts, claims, verifications
4. **Ingestion engine** for fetching, validating, and storing Apify data

## Architecture

### Layer 1: Data Validation & Schema

```python
from app.core.ingestion.schemas import ApifyFacebookPost

# Validate raw Apify data
post = ApifyFacebookPost(**raw_post_data)
quality_score = post.quality_score()  # 0.0 - 1.0
```

### Language Detection

```python
from app.core.ingestion.lang_detect import detect_language

lang_code, confidence = detect_language("গতকাল সরকার নতুন নীতি ঘোষণা করেছে।")
# Returns ("bn", 0.95)
```

### Database Models

```python
from app.web.models.verification import (
    SocialMediaPost,  # Original social media post
    Claim,            # Extracted claim from post
    VerificationResult, # Verification results (Layers 4-6)
    FactCheckSource,  # External fact-check sources
    ExternalFactCheck # Cached fact-check results
)
```

### Ingestion Engine

```python
from app.core.ingestion.ingestor import ApifyIngestor

# Ingest from Apify dataset URL
ingestor = ApifyIngestor(dataset_url="https://api.apify.com/v2/datasets/oPQI8x1X4nfpM6l5V/items?format=json")
success, failed = ingestor.ingest_dataset(max_posts=100)
```

## CLI Usage

```bash
# Create verification tables
python app/core/ingestion/cli.py create-tables

# Ingest from Apify dataset URL
python app/core/ingestion/cli.py ingest-url --url "https://api.apify.com/v2/datasets/oPQI8x1X4nfpM6l5V/items?format=json"

# Ingest from local JSON file
python app/core/ingestion/cli.py ingest-file --file path/to/apify_data.json

# Test language detection
python app/core/ingestion/cli.py test-language --text "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।"
```

## Testing

```bash
python app/core/ingestion/test_ingestion.py
```

## Next Steps

After ingestion, the pipeline needs:

1. **Claim extraction** (Layer 3) - extract factual claims from posts
2. **Fact-check lookup** (Layer 4) - check against external sources
3. **Temporal verification** (Layer 5) - check timeline consistency
4. **RAG analysis** (Layer 6) - LLM analysis grounded in evidence
5. **Confidence scoring** (Layer 7) - composite verification score

## Design Principles

- **Global**: Designed for multiple languages (EN + BN + extension)
- **Scalable**: PostgreSQL-ready, with SQLite fallback
- **Validated**: Pydantic schema validation for data quality
- **Extensible**: Modular design for adding new platforms/sources