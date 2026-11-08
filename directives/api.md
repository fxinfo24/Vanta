# Vanta API Documentation

## Overview
Vanta provides a comprehensive RESTful API for social media profile analysis across 10+ major platforms. The API leverages universal data collection through ScrapeCreators and advanced AI analysis via OpenRouter, enabling real-time insights from Twitter/X, Instagram, LinkedIn, TikTok, Facebook, YouTube, Snapchat, Pinterest, Reddit, and GitHub.

## Supported Platforms

- **Twitter/X**: Profile data, tweets, engagement metrics, verification status
- **Instagram**: Profile information, post data, business accounts
- **LinkedIn**: Professional profiles, company data, network analysis
- **TikTok**: Creator profiles, video metrics, follower engagement
- **Facebook**: Public profiles, page data, community insights
- **YouTube**: Channel analysis, subscriber data, video performance
- **Snapchat**: User profiles, snap metrics, audience insights
- **Pinterest**: Board analytics, pin performance, trending content
- **Reddit**: User karma, community analysis, post engagement
- **GitHub**: Developer profiles, repository data, contribution analysis

**Total Coverage**: 10+ major social media and professional platforms

## API Endpoints

### Authentication
This repository's Flask API routes do **not** currently implement authentication (JWT/API keys).

If you are deploying publicly, you should add auth at the Flask layer (e.g., `flask-login`, JWT middleware) or behind an API gateway.

### Core Task/Analysis Endpoints (implemented)

#### POST /api/analyze
Create a new analysis task.

**Request Body:**
```json
{
  "platform": "twitter",
  "profile_id": "elonmusk"
}
```

**Response:** `202 Accepted` with a `task` object.

#### GET /api/tasks
List tasks with optional filters:
- Query params: `platform`, `status`, `limit` (default 10), `offset` (default 0)

#### GET /api/tasks/{task_id}
Get full task details.

#### GET /api/tasks/{task_id}/status
Get task status for polling (lightweight).

#### POST /api/tasks/{task_id}/cancel
Cancel a task (only if status is PENDING or PROCESSING).

#### GET /api/tasks/{task_id}/results
Return JSON results for a completed task.

#### GET /api/tasks/{task_id}/download
Download results as a `.json` file.

### Stats Endpoints (implemented)

#### GET /api/stats/platform-distribution
Returns a count of tasks by platform.

#### GET /api/stats/completion-rate
Returns completion-rate metrics for tasks.

### Verification Endpoints (Product B — consolidated into the same Flask app, implemented)

Product B (7-layer verification) shares the same DB + app as Product A. No features removed; CLIs unchanged.

- `POST /api/verification/post` — manual ingest `{platform, profile_id, text, author_name?, post_url?}` → `SocialMediaPost` (201)
- `POST /api/verification/post/from-task/{task_id}` — bridge: completed Product A `Task.result_data` (bio/display/executive_summary) → `SocialMediaPost` (200/201)
- `POST /api/verification/task/{task_id}/run` — one-call: bridge + Layer3→7 pipeline for that post's claims
- `POST /api/verification/pipeline` — `{post_id?, limit?}`: extract (Layer3) then Layers 4→5→6→7 per claim. Returns per-claim stage summary; RAG skips cleanly to `UNVERIFIABLE` without evidence/API key.
- `GET /api/verification/posts?limit=` · `GET /api/verification/claims?limit=` · `GET /api/verification/claim/{claim_id}` · `GET /api/verification/results?limit=`

Layer order: ClaimExtractor → `FactCheckEngine` (google+mock) → `TemporalVerifier` (newsapi/wayback) → `RAGEngine` (openrouter, grounding-gated) → `ConfidenceScorer` (writes `layer_7` to `evidence_chain`, updates `composite_verification_score`). All read/write the consolidated `app/web/models/verification.py` superset schema (`verification_status` mirrors legacy `status`; `text` mirrors `content`; `timestamp` = platform time).

Frontend: `frontend/src/services/api.ts` now exposes `createVerificationPost`, `createPostFromTask`, `verifyTask`, `runVerificationPipeline`, `listVerificationPosts/Claims/Results`, `getVerificationClaim`.

**DB note:** verification tables (`social_media_posts`, `claims`, `verification_results`, `fact_check_sources`, `external_fact_checks`) are `db.create_all()`-ed at startup (SQLite/dev safe). On Postgres prefer `flask db migrate && flask db upgrade` — existing Integer-PK verification tables need a table rebuild to adopt String PKs.

### Not implemented in this repo (documentation placeholders)
The following concepts are **not** implemented by the current Flask routes in this repository:
- WebSockets for progress updates
- Team management / enterprise endpoints
- Usage/billing endpoints
- Official Python/JS SDKs

## Rate Limits

- **Free Tier**: 1,000 requests/month
- **Basic Tier**: 10,000 requests/month  
- **Professional Tier**: 50,000 requests/month
- **Enterprise Tier**: 200,000 requests/month

## Error Codes

- `400`: Bad Request - Invalid parameters
- `401`: Unauthorized - Invalid authentication
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource not found
- `429`: Rate Limited - Too many requests
- `500`: Internal Server Error - Server issue

## SDKs and Libraries

There are no official Python/JS SDK packages included in this repository.

### Python (example using raw HTTP)
```python
import requests

resp = requests.post(
    "http://localhost:5000/api/analyze",
    json={"platform": "twitter", "profile_id": "username"},
)
resp.raise_for_status()
print(resp.json())
```

### JavaScript (example using fetch)
```javascript
const resp = await fetch('http://localhost:5000/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ platform: 'twitter', profile_id: 'username' }),
});
console.log(await resp.json());
```
