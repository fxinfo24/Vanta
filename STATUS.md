# Vanta — Current Status (consolidated)

> Single source of truth for project state. This file replaces the former
> `PROGRESS_SUMMARY.md`, `PROGRESS_LAYER4_COMPLETE.md`, `PROGRESS_LAYER5_COMPLETE.md`,
> and `ARCHITECTURE_COMPLETE.md` (deleted: stale milestone snapshots / inflated claims).

## What Vanta is

Two products consolidated into **one Flask app** (`app/web/app.py:create_app()`), one DB:

- **Product A — Social intelligence:** Flask → `SocialMediaAnalyzer` (`app/core/analyzer.py`)
  → `DeepDossierCollector` (`app/core/deep_collector.py`) → `IntelligenceAnalyzer`
  (core + belief + consumer + behavioral) → OpenRouter LLM.
  Data: ScrapeCreators (primary, 21 platforms), Apify fallback (Facebook).
- **Product B — 7-layer verification:** `app/core/{ingestion, normalization, claim_extraction,
  fact_check, temporal_verification, rag_analysis, evidence}`. Originally CLI-only;
  now wired into the same Flask app + DB (superset schema in
  `app/web/models/verification.py`, migration `c7d8e9f0a1b2`). No features removed.

## Verified live (as of Nov 2026)

- Backend: Flask on :5000 (`bin/run.py --web`), frontend Vite on :5173, `GET /api/health` = healthy.
- Facebook E2E (`facebook.com/AzizMdArif`, task 12): Arif Aziz, 2,061 followers/likes,
  14 talking-about, category "Digital creator", real bio, **40 content items** (30+ pagination),
  4 comments, belief analysis with evidence calibration. Stored in `Task.result_data` (DB canonical).
- OpenRouter: default `nvidia/nemotron-3-ultra-550b-a55b:free` (override via `OPENROUTER_MODEL`).
  `load_dotenv(override=True)` — a stale shell env var previously shadowed `.env` (root cause of 401s).
- Apify: token valid (`hermes_blazer`). Facebook actor `apify/facebook-posts-scraper` (verified 200;
  old `apify/facebook-scraper` 404s — do not use). **Blocked:** free usage exhausted ($0.004 left),
  fallback code is wired but runs need a paid plan (console.apify.com/billing).
- ScrapeCreators: key in `.env`; balance visible only via dashboard / `credits_remaining` in responses
  (no credits API endpoint). New key: ~99 credits at last check.
- Tests: `pytest` **53 passed / 0 failed** (Nov 2026). The 4 former failures were fixed at root cause: `preprocess_text` now honours its contract (strips URLs + `,.!?`); `analyze_writing_style` vocabulary diversity is uni+bigram TTR and complexity no longer saturates at 1.0; `test_analyze_profile` / `test_full_analysis_flow` were stale (patched legacy `DataCollector` while the analyzer uses `DeepDossierCollector`, causing real API calls that burned ScrapeCreators credits) — they now mock `create_deep_collector` + the intelligence engine, so tests are hermetic. A syntax corruption introduced mid-edit (`}def`) was caught by the same tests and repaired.
  `tsc --noEmit` clean. ESLint: 103 pre-existing warnings, 0 errors.
- 7-layer verification E2E (verified live, Nov 2026): ingest → extract (2 FACTUAL claims,
  check-worthiness 0.6) → Layers 4–7 all execute, evidence_chain persists `layer_4..7`. Keys now wired: `GOOGLE_FACT_CHECK_API_KEY` + `NEWSAPI_KEY` in `.env` (never commit). **Proven real verdict:** claim "2020 US election was stolen / Trump won" → Layer 4 `VERIFIED_FALSE` matched to **USA Today** ("President Donald Trump did not win 2020 election", similarity 0.347), final status `VERIFIED_FALSE`, composite 0.625, Layer 7 `CONFIDENT`. Layer 5 NewsAPI found 16 real articles; Layer 6 Nemotron returned grounded reasoning. **Semantic matcher (Nov 2026):** Layer 4 now embeds claim + fact-checks via OpenRouter `/embeddings` (`openai/text-embedding-3-small`, 1536-dim, live 200; override `EMBEDDING_MODEL`), cosine threshold 0.55 (measured: paraphrase 0.695–0.703, related-but-different 0.37, unrelated ≤0.11). Same USA Today match now scores **0.703** (was 0.347 lexical). If the embedding API fails, a pure-Python TF-IDF cosine is used and labelled `tfidf_fallback` on every match — never silently presented as semantic. **Evidence corpus (Layer 6):** live discovery per claim — web-fetches real page text of L4/L5 URLs, Wikipedia REST summary, GDELT wide-window, NewsAPI ±365d — ranked by embedding similarity; proven live (evidence_count 7–8, Wikipedia "Big lie" article retrieved). No vector DB (no dependency); it is a live-fetched ranked corpus, not a persisted index. **Human review:** `POST /verification/claim/<id>/review` (approve/override, reviewer + note) writes `human_override` into `layer_7` and clears `needs_human_review` — verified live incl. 400 on invalid verdict. **Duplicate claims fixed:** root cause was Python `hash()` (salted per process) so dedup never matched after restart; now stable SHA-256 of normalized text — re-run verified: claim count stays 1. **Layer 5:** GDELT + Wikipedia added to default sources; relevance is embedding cosine (top article 0.518 → `verified: True`, was TF-IDF 0.144 false-negative); aggregation bug fixed (failed sources were excluded from confidence, inflating L5 to 1.0 — now honest PLAUSIBLE 0.51). Further hardening (Nov 2026): Google client now queries two phrasings (full claim + keyword phrase) and unions results deduped by URL — verified live: 10 unique results for the election claim (mitigates ranking flakiness; ranking itself is still non-deterministic upstream). GDELT Layer 5 window: if the claim names a different year than the post date, it searches that named year instead of ±15d around the post (historical claims). Wikipedia historical lookup fixed: now fetches the newest revision at/before the target date via `rvstart`/`rvdir=older` (old code fetched the 50 oldest revisions) — verified live: "2020 United States presidential election", revision 2026-11-06. ClaimBuster client no longer returns mock heuristic scores: without a key it returns `score: None, source: "unavailable"` and filtering passes claims through (see provider table). `fullfact` client honestly returns `[]` instead of a fabricated example. DB cleanup: 3 pre-existing duplicate claims (salted-hash era) removed, keeping the verified copy (backup `data/vanta.db.pre_dedupe_bak`). Remaining caveats: Google ranking is still non-deterministic upstream (multi-query mitigates, cannot eliminate); GDELT contemporaneous window finds nothing when a claim names no year (corpus wide-window covers this); ClaimBuster still has no key (see below). Live-DB schema bug found + fixed: `social_media_posts.id` was INTEGER (old schema) vs String PK model → every `/verification/post` 500'd with `datatype mismatch`; verification tables were empty so they were dropped + recreated (backup: `data/vanta.db.bak`). Bugs fixed Nov 2026: Google client parsed a non-existent nested `claim` wrapper (claim text always empty → matcher dropped everything); engine `maxAgeDays` 365→3650; Layer 6 hardcoded `claude-3.5-sonnet` (404) → `OPENROUTER_MODEL`/Nemotron; Layer 6 no longer overwrites a concrete L4 verdict with evidence-less `UNVERIFIABLE`; JSON `evidence_chain` in-place mutation was being lost (now reassigned in L5/L6/L7); NewsAPI stopwords fixed.

## Data providers (honest)

| Provider | Role | Status |
|---|---|---|
| ScrapeCreators | Primary fetcher (profile/posts/reels/comments/photos/events) | Working, credit-limited |
| Apify | Fallback when ScrapeCreators credits exhaust (402 → `CREDITS_EXHAUSTED`) | Wired; billing-blocked |
| OpenRouter | LLM analysis (downstream, orthogonal to scraping) | Working (Nemotron free) |
| Google Fact Check / NewsAPI | Verification Layer 4/5 | Working (keys in `.env`); embeddings via OpenRouter |
| ClaimBuster | Check-worthiness scoring | **No key yet.** Client fixed to the real v2 API (`POST claimbuster.org/api/v2/score/text/`, verified live; old code POSTed a non-existent path) and TLS fixed via `truststore` (their Internet2 InCommon CA is not in certifi, so `requests` fails verification everywhere). Registration form is at `claimbuster.org/api/request/key/` but is gated by **reCAPTCHA**, which the agent cannot bypass — the account owner must submit it (~2 min: name, `videotaletactician@gmail.com`, title, org, project URL `https://github.com/fxinfo24/Vanta`, usage description), verify the email, then paste `CLAIMBUSTER_API_KEY` into `.env`. Until then the client honestly returns `score: None, source: "unavailable"` (never mock scores) |

Not implemented in this repo: auth on Flask routes, WebSockets, team/billing endpoints
(`app/enterprise/*` modules exist but are **not** wired to any route), official SDKs.

## Known limits (not fabricated around)

- Facebook `following_count` / total `posts_count` are not exposed by the ScrapeCreators API → stay 0.
- Vercel frontend (`profile-scope.vercel.app`) has **no live backend**: dead Railway rewrites were
  removed from `vercel.json`; `VITE_API_BASE_URL` must be set to a deployed backend URL.
  Local stack (Flask :5000 + Vite :5173) is the working deployment today.
- Migrations: fresh DBs use `db.create_all()`; existing DBs run
  `flask db stamp 6a95d7308ea3 && flask db upgrade` (adds `task.result_data`, verification superset cols).

## Docs map

| Doc | Purpose |
|---|---|
| `README.md` | Project overview + quick start |
| `AGENTS.md` | Agent instructions + session resume prompt |
| `STATUS.md` (this file) | Current verified state |
| `directives/api.md` | REST API reference |
| `directives/setup_guide.md` | Setup + API keys |
| `directives/development.md` | Dev workflows |
| `directives/HANDOVER.md` | Session handover |
| `directives/CODEBASE_ASSESSMENT.md` | Strategic assessment/roadmap |
| `directives/desktop_mobile.md` / `ui_overhaul.md` | Desktop/mobile + UI notes |
| `app/core/*/README.md` | Per-module docs (ingestion, claim_extraction, fact_check, temporal_verification) |
| `tests/README.md` | Test guide |
