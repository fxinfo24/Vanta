# Vanta: Temporal & Contextual Verification (Layer 5)

Verify claims against timeline and context using global event databases, historical archives, and contemporaneous reporting.

## Overview

Layer 5 adds **timeline consistency** and **contextual verification** to claims by checking:
- **GDELT**: Global event database (was this mentioned in news at the time?)
- **Wayback Machine**: Historical webpage verification (did this URL exist then?)
- **NewsAPI**: Contemporaneous reporting (what was being reported at that time?)
- **Wikipedia**: Historical facts (what was known as of the claim date?)

## Features

1. **Temporal Plausibility Scoring**:
   - HIGHLY_PLAUSIBLE (confidence ≥ 0.7)
   - PLAUSIBLE (confidence ≥ 0.4)
   - WEAK_EVIDENCE (confidence ≥ 0.2)
   - IMPLAUSIBLE (confidence < 0.2)

2. **Multi-Source Verification**:
   - News coverage verification
   - URL existence verification
   - Global event matching
   - Historical fact checking

3. **Composite Confidence Scoring**:
   - Weighted average: 60% Layer 4 (fact-check) + 40% Layer 5 (temporal)
   - Complete evidence chain stored

## Architecture

### Core Components

```python
GDELTClient          # Global Database of Events, Language, and Tone
WaybackClient        # archive.org Wayback Machine
NewsAPIClient       # Contemporaneous news articles
WikipediaClient     # Historical Wikipedia state

TemporalVerifier    # Main verification engine
```

### Database Integration

Layer 5 results are stored in `VerificationResult.evidence_chain["layer_5"]`:

```json
{
  "temporal_plausibility": "HIGHLY_PLAUSIBLE",
  "confidence": 0.85,
  "claim_date": "2024-01-15",
  "verifications": {
    "news": {...},
    "urls": {...},
    "events": {...},
    "facts": {...}
  }
}
```

## Usage

### CLI Commands

```bash
# Test all temporal APIs
python app/core/temporal_verification/cli.py test

# Verify a single claim temporally
python app/core/temporal_verification/cli.py verify claim_123

# Batch verify claims
python app/core/temporal_verification/cli.py batch --limit 100

# View statistics
python app/core/temporal_verification/cli.py stats
```

### Programmatic Usage

```python
from app.core.temporal_verification import create_temporal_verifier

# Create verifier
verifier = create_temporal_verifier(
    sources=["newsapi", "wayback", "gdelt"]
)

# Verify a claim
result = verifier.verify_claim_temporally(claim)

# Batch processing
stats = verifier.process_unverified_claims(limit=50)
```

## How It Works

### 1. Timeline Verification Pipeline

```
Claim: "Yesterday, the government announced new policies"
        ↓ (Extract date from post)
Claim Date: 2024-03-15
        ↓ (Query NewsAPI)
NewsAPI → Articles from March 8-22
        ↓ (Check Wayback)
URL "example.com/policy" → Archived on March 14
        ↓ (Query GDELT)
GDELT → "policy announcement" events on March 15
        ↓ (Aggregate)
Temporal Plausibility: HIGHLY_PLAUSIBLE (0.85)
```

### 2. Plausibility Calculation

```
Total Confidence = Weighted Average of:
- News coverage (40%): Do contemporaneous reports exist?
- URL verification (20%): Did referenced URLs exist?
- Global events (30%): Was event in global database?
- Historical facts (10%): What was known then?

Confidence ≥ 0.7 → HIGHLY_PLAUSIBLE
Confidence ≥ 0.4 → PLAUSIBLE  
Confidence ≥ 0.2 → WEAK_EVIDENCE
Confidence < 0.2 → IMPLAUSIBLE
```

### 3. Cross-Language Support

- Bengali dates automatically parsed
- Country-specific queries (default: BD for Bangladesh)
- Language-aware news searches

## Configuration

### Environment Variables

```bash
# NewsAPI (optional but recommended)
NEWSAPI_KEY=your_api_key_here

# GDELT (no API key required)
# Wayback Machine (no API key required)
# Wikipedia (no API key required)
```

### Verifier Configuration

```python
verifier = TemporalVerifier(
    sources=["newsapi", "wayback", "gdelt"],  # Which APIs to use
    min_confidence=0.3                         # Minimum confidence threshold
)
```

## Example Results

```json
{
  "verified": true,
  "temporal_plausibility": "HIGHLY_PLAUSIBLE",
  "confidence": 0.82,
  "claim_date": "2024-03-15",
  "verifications": {
    "news": {
      "verified": true,
      "reason": "Found 12 news articles (avg relevance: 0.65)",
      "total_articles": 12,
      "confidence": 0.78
    },
    "urls": {
      "verified": true,
      "reason": "Verified 2/2 URLs",
      "confidence": 1.0
    },
    "events": {
      "verified": true,
      "reason": "Found 5 global events (avg relevance: 0.42)",
      "confidence": 0.63
    }
  }
}
```

## Composite Score (Layer 4 + Layer 5)

Claims now have a **composite verification score**:

```
Composite Score = (Layer4_confidence × 0.6) + (Layer5_confidence × 0.4)

Example:
- Layer 4 (fact-check): 0.9 (VERIFIED_TRUE)
- Layer 5 (temporal): 0.85 (HIGHLY_PLAUSIBLE)
- Composite: (0.9 × 0.6) + (0.85 × 0.4) = 0.88
```

## Next Layer (Layer 6: AI RAG Analysis)

Verified and temporally plausible claims are now ready for:
1. **Evidence retrieval** from Layers 4-5
2. **RAG-based LLM analysis** with evidence constraints
3. **Citation verification** to prevent hallucinations
4. **Multi-LLM cross-validation**

## Limitations & Improvements

### Current Limitations
- NewsAPI requires API key for production
- Simple keyword matching for news relevance
- Limited to 30-day date ranges for free APIs

### Future Improvements
- Add more news sources (Reuters, AFP, AP)
- Fine-tuned relevance models
- Advanced temporal event extraction
- Historical news archive integration