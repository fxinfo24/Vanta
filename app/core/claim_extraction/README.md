# Vanta: Claim Extraction (Layer 3)

Extract factual claims from social media posts for verification.

## Overview

Layer 3 extracts factual claims from social media posts, classifying them as:
- **Factual:** Verifiable statements (e.g., "The government announced new policies")
- **Opinion:** Subjective statements (e.g., "I think this is a good decision")
- **Satire/Spam/Other:** Non-verifiable content

## Features

1. **Sentence Splitting:** Separates posts into individual sentences (EN + BN)
2. **Claim Classification:** Identifies factual vs opinion vs other
3. **Entity Extraction:** Basic named entity recognition (dates, numbers)
4. **Check-worthiness Scoring:** Determines which claims are worth fact-checking
5. **Database Integration:** Stores extracted claims in PostgreSQL/SQLite

## Usage

### CLI Commands

```bash
# Test extraction on sample text
python app/core/claim_extraction/cli.py test --language bn

# Process unprocessed posts
python app/core/claim_extraction/cli.py process --limit 50

# View statistics
python app/core/claim_extraction/cli.py stats
```

### Programmatic Usage

```python
from app.core.claim_extraction import ClaimExtractor

# Extract claims from text
extractor = ClaimExtractor()
claims = extractor.extract_claims_from_text(
    "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।",
    language_code="bn"
)

# Process unprocessed posts
processed, claims_extracted = batch_extract_claims(limit=100)
```

## Architecture

### Simple → Advanced Pipeline

**Current (Simple):**
- Regex patterns for claim detection
- Keyword-based classification
- Heuristic check-worthiness scoring

**Future (Advanced):**
- spaCy/polyglot for Bengali sentence splitting
- XLM-RoBERTa for claim classification
- Proper NER for Bengali entity extraction
- Fine-tuned check-worthiness model

### Database Schema

Claims are stored in the `claims` table:
```sql
id | post_id | claim_text | claim_type | check_worthiness_score | entities | detected_language
```

## Algorithm

1. **Input:** Social media post text
2. **Sentence Splitting:** Divide text into sentences
3. **Language Detection:** Determine language (EN/BN)
4. **Classification:** Identify factual vs opinion
5. **Entity Extraction:** Extract dates, numbers, entities
6. **Check-worthiness:** Score claim (0.0-1.0)
7. **Storage:** Save to database with metadata

## Examples

**Bengali Input:**
```
গতকাল সরকার নতুন নীতি ঘোষণা করেছে। 
এই নীতির ফলে ১০ লক্ষ মানুষ উপকৃত হবে। 
আমি মনে করি এটি ভাল সিদ্ধান্ত।
```

**Extracted Claims:**
1. "গতকাল সরকার নতুন নীতি ঘোষণা করেছে"
   - Type: Factual
   - Checkworthiness: 0.7
   - Entities: [DATE: "গতকাল"]

2. "এই নীতির ফলে ১০ লক্ষ মানুষ উপকৃত হবে"
   - Type: Factual  
   - Checkworthiness: 0.8
   - Entities: [CARDINAL: "১০ লক্ষ"]

3. "আমি মনে করি এটি ভাল সিদ্ধান্ত"
   - Type: Opinion
   - Checkworthiness: 0.2

## Next Layer (Layer 4: Fact-Checking)

Extracted claims are now ready for:
1. Google Fact Check API lookup
2. Temporal verification (GDELT, Wayback Machine)
3. AI RAG analysis with evidence constraints

## Token-Efficient Design

- Minimal dependencies (no heavy NLP models by default)
- Progressive enhancement (start simple, add complexity)
- Batch processing for efficiency
- Database indexes for performance