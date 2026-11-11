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
Every `/api` route except `GET /api/health` and the `POST /api/auth/*` routes requires a JWT (24h expiry) in the `Authorization: Bearer <token>` header. Requests without a valid token return **401**; cross-user access returns **404** (never 403, so resource existence doesn't leak). Each user only ever sees their own tasks, posts, claims, verification results, and settings.

#### POST /api/auth/register — `{email, password, username?, first_name?, last_name?}` → `{user, token}` (201; 409 duplicate email/username; 400 invalid email or password < 8 chars)
#### POST /api/auth/login — `{email, password}` → `{user, token}` (200; generic 401 on bad credentials — doesn't reveal which field was wrong)
#### GET /api/auth/me — current user (requires token)
#### POST /api/auth/change-password — `{current_password, new_password}` → `{message}` (401 wrong current; 400 new < 8 chars)

### Settings + BYOK (implemented)

Per-user settings live in the profile menu → **Settings**. Keys are stored **Fernet-encrypted** (key derived from `BYOK_ENCRYPTION_KEY` or `SECRET_KEY`) and are **never returned in plaintext** — responses only report per-provider `configured`/`source`/`hint` (masked last-4). Resolution order per analysis run: user's own key → server env var → provider honestly reports unavailable (never mock data). A user's keys never apply to another user's runs.

#### GET /api/settings — `{profile, preferences: {default_mode, preferred_model}, available_models, byok: {provider: {label, configured, source, hint}}}`
#### PUT /api/settings — partial update; accepted keys: `first_name`, `last_name`, `username`, `default_mode` (`quick`|`deep`), `preferred_model` (catalog id or `null`), `byok: {provider: key}` (set) or `byok: {provider: ""}` (remove). Returns the GET shape. Using `POST /api/analyze` without `mode` applies the saved `default_mode`.

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
Download results (`?format=html|pdf|json`, default `json`). Requires the Bearer token — browsers can't attach it via `window.open()`, so the frontend fetches the file through the authenticated API client and opens the resulting blob (new tab for html/pdf print view, file download for json).

### Apify Endpoints (implemented)

- `GET /api/apify/health` — token check (`{configured, valid, user}`), no Actor run / no cost.
- `POST /api/apify/run` — run an Apify actor directly: `{actor, input}` → dataset items. Facebook fallback actor is `apify/facebook-posts-scraper` (verified live; do not use the 404 `apify/facebook-scraper`).
- Automatic fallback: when ScrapeCreators returns 402 (`CREDITS_EXHAUSTED`), `DeepDossierCollector` falls back to Apify for Facebook profile+posts. Note: Apify free-tier usage must cover the run (raise limit at console.apify.com/billing).

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
- `POST /api/verification/job` — **server-to-server only** (QStash destination; no user JWT, requires a valid `Upstash-Signature` over the body and URL). Body `{post_id, max_claims?}` runs Layers 3→7 for that one post and returns counts — it must never return per-user data. Returns 500 on failure so QStash retries; a retry resumes because claims that already have Layers 4 and 7 are skipped.
- Dispatch order when a caller does not pass `?wait=1`: QStash (if `QSTASH_TOKEN` + signing key set) → Celery (if `FORCE_CELERY=true` + `REDIS_URL`) → background thread. All three run the same `run_verification_for_posts`; the response carries `mode` and the caller polls `GET /api/verification/results`.
- `POST /api/verification/claim/{claim_id}/review` — human review `{verdict: VERIFIED_TRUE|VERIFIED_FALSE|MISLEADING|UNVERIFIABLE, action: approve|override, reviewer?, note?}` → writes `human_override` into `evidence_chain.layer_7`, clears `needs_human_review`, applies verdict on `override` (400 on invalid verdict; 404 if claim/verdict missing)

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
