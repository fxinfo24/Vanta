# Vanta: Fact-Check API Integration (Layer 4)

Connect claims to external fact-check databases using semantic similarity matching.

## Overview

Layer 4 queries external fact-check APIs (Google Fact Check, Full Fact, etc.) and matches claims to existing fact-checks using semantic similarity.

## Features

1. **Multiple API Clients:**
   - Google Fact Check Tools API
   - Full Fact API (UK-focused)
   - Mock client for development

2. **Semantic Similarity Matching:**
   - Cross-language matching (BN ↔ EN)
   - Multi-method similarity scoring
   - Configurable similarity thresholds

3. **Result Aggregation:**
   - Combine results from multiple sources
   - Generate confidence-weighted verdicts
   - Store complete evidence chain

4. **Caching & Rate Limiting:**
   - Avoid duplicate API calls
   - Respect API rate limits
   - Cache results in database

## Architecture

### Core Components

```python
FactCheckClient          # Base API client
GoogleFactCheckClient    # Google Fact Check API
FullFactClient          # Full Fact API (UK)
MockFactCheckClient     # Mock data for development

FactCheckMatcher        # Semantic similarity matching
FactCheckEngine         # Orchestration & database integration
```

### Database Integration

```python
VerificationResult       # Stores Layer 4 results
FactCheckSource         # Registered fact-check APIs
ExternalFactCheck       # Cached fact-check data
```

## Usage

### CLI Commands

```bash
# Test API connections
python app/core/fact_check/cli.py test --sources google mock

# Verify a single claim
python app/core/fact_check/cli.py verify claim_123

# Batch verify unprocessed claims
python app/core/fact_check/cli.py batch --limit 100

# View results
python app/core/fact_check/cli.py results

# Register fact-check sources
python app/core/fact_check/cli.py register-sources
```

### Programmatic Usage

```python
from app.core.fact_check import create_fact_check_engine

# Create engine
engine = create_fact_check_engine(
    sources=["google", "mock"],
    similarity_threshold=0.3
)

# Verify a claim
result = engine.fact_check_claim(claim)

# Batch processing
stats = engine.process_unverified_claims(limit=50)
```

## How It Works

### 1. Claim → Fact-Check Matching

```
Claim: "গতকাল সরকার নতুন নীতি ঘোষণা করেছে"
        ↓ (Translate keywords)
Claim (keywords): "yesterday government new policy announce"
        ↓ (API Query)
Google Fact Check API → Search for similar claims
        ↓ (Similarity Scoring)
Match found: 75% similarity
        ↓ (Verdict Aggregation)
VERIFIED_TRUE (confidence: 0.75)
```

### 2. Similarity Algorithms

Three methods combined:
1. **Sequence Matching**: Character-level similarity
2. **Word Overlap**: Jaccard similarity of word sets  
3. **Keyword Matching**: Boost for matching important keywords

### 3. Cross-Language Support

- Bengali claims matched to English fact-checks via keyword translation
- Language-specific similarity rules
- Configurable language compatibility

## Configuration

### Environment Variables

```bash
# Google Fact Check API
GOOGLE_FACT_CHECK_API_KEY=your_api_key_here

# Full Fact API (if available)
FULL_FACT_API_KEY=your_api_key_here
```

### Engine Configuration

```python
engine = FactCheckEngine(
    sources=["google", "mock"],      # Which APIs to use
    similarity_threshold=0.3,        # Minimum match score
    cache_results=True              # Cache API responses
)
```

## Example Results

```json
{
  "claim_text": "10 million people will benefit from the new policy",
  "verdict_summary": {
    "verdict": "VERIFIED_TRUE",
    "confidence": 0.82,
    "sources": ["google_fact_check"],
    "summary": "Matched to Google Fact Check: True"
  },
  "matches_found": 2,
  "top_matches": [
    {
      "source": "google_fact_check",
      "claim_text": "8-12 million people will benefit from policy",
      "verdict": "True",
      "similarity_score": 0.78,
      "url": "https://factcheck.example.com/123"
    }
  ]
}
```

## Next Layer (Layer 5: Temporal Verification)

Verified claims are now ready for:
1. **GDELT API**: Check if events match global news timeline
2. **Wayback Machine**: Historical webpage verification
3. **NewsAPI**: Contemporaneous reporting verification

## Limitations & Improvements

### Current Limitations
- Simple keyword-based cross-language matching
- Limited fact-check source coverage
- No advanced NLP for similarity

### Future Improvements
- Sentence transformers for semantic similarity
- More fact-check sources (Reuters, AFP, Snopes)
- Fine-tuned cross-language models
- Real-time API monitoring for new fact-checks