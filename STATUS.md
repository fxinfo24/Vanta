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
- Tests: `pytest` **78 passed / 0 failed** (Nov 2026). The 4 former failures were fixed at root cause: `preprocess_text` now honours its contract (strips URLs + `,.!?`); `analyze_writing_style` vocabulary diversity is uni+bigram TTR and complexity no longer saturates at 1.0; `test_analyze_profile` / `test_full_analysis_flow` were stale (patched legacy `DataCollector` while the analyzer uses `DeepDossierCollector`, causing real API calls that burned ScrapeCreators credits) — they now mock `create_deep_collector` + the intelligence engine, so tests are hermetic. A syntax corruption introduced mid-edit (`}def`) was caught by the same tests and repaired.
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

## User accounts, settings & BYOK (Nov 2026)

- **Auth:** `POST /api/auth/register|login` + `GET /api/auth/me`, JWT (Bearer, 24h) guarding **every** `/api` route (only `/api/health` + `/auth/*` public). All tasks/posts/claims/verification are scoped to the authenticated user (404 cross-user — existence never leaks). `POST /api/auth/change-password`. Frontend: Login/Register view + profile dropdown (Settings, Log out) in the header. Password hashing via bcrypt (`PyJWT` + `bcrypt` added to requirements).
- **Settings:** `GET|PUT /api/settings` — profile fields, `default_mode` (quick/deep, applied when `POST /api/analyze` omits mode), `preferred_model` (validated against the OpenRouter catalog; applied per-request), and **BYOK**: per-provider API keys (OpenRouter, ScrapeCreators, NewsAPI, Google Fact Check, ClaimBuster, Apify) stored **Fernet-encrypted** in `user_settings.byok_keys_enc` (key derived from `BYOK_ENCRYPTION_KEY` or `SECRET_KEY` — rotating the secret makes stored keys undecryptable; users re-enter them). API responses never contain key material (masked `••••xxxx` hints + configured/source only).
- **BYOK resolution:** per-run ContextVar installed at every entry point (request guard for sync routes; background thread + Celery worker resolve from `Task.user_id`). Clients resolve user key → server env, lazily per request (singletons incl. `OpenRouterClient` refresh auth per call; analyzer collector cache is keyed by a key fingerprint so cached clients can't leak keys between users). Missing keys degrade honestly (no mock data; ClaimBuster stays `unavailable` until a key exists).
- **Verified live:** register/login/scoping matrix (200/401/404/duplicates/invalid token — all correct); settings round-trip + masking; **BYOK proven**: garbage Apify key saved → `GET /api/apify/health` 401 with user key, cleared → 200 with server token; garbage OpenRouter key in settings → analysis `consumer_profile` shows `Invalid API key` (env key was NOT used); raw DB blob contains no plaintext. Tests: **63 passed / 0 failed** (58 → +5 settings/BYOK/change-password/isolation tests); `tsc && vite build` clean. Migration `d1e2f3a4b5c6` adds `users` + `user_id` + `user_settings` (existing DBs built pre-auth used `db.create_all()` + manual ALTER; `flask db upgrade` on a fresh DB is the prod path).
- **Legacy data:** pre-auth rows (`user_id NULL`, e.g. task 12's AzizMdArif dossier) are hidden from every user by design (privacy-safe default). Claim them with `UPDATE task SET user_id=<id> WHERE user_id IS NULL` (same for `social_media_posts`) once signed up. *Done:* the owner's account (`fxinfo24@gmail.com`, id 8) claimed tasks 6–12 + 4 verification posts; 5 older legacy tasks (ids 1–5) deleted (backups in `data/backups/`).
- **Frontend transport fixes (Nov 2026):** signup "Network Error" root cause was a stale `VITE_API_BASE_URL=http://localhost:5000` (no `/api`) exported to the Vite process, bypassing the dev proxy → `register` hit a 404 and axios reported "Network Error". `api.ts` now always uses `/api` in dev (`import.meta.env.DEV` branch); `vite.config.ts` proxy default `localhost:5000`. Print/PDF 401: export used bare `window.open()` which can't carry the Bearer token → 401; now `downloadTaskResults()` fetches the blob through the authenticated client and opens `URL.createObjectURL()` (new tab for html/pdf, download for json). Both verified live.
- **Results-section mapping fixes (Nov 2026):** sections *were* analyzed but the frontend read wrong keys — `POLITICAL_COMPASS`/`SOCIAL_VALUES` (underscores) vs `['POLITICAL COMPASS']` (spaces); Big 5 stored as `content_analysis.personality_traits` vs frontend `psychological_profile` (never existed); ConsumerTab rendered `predicted_purchases` objects raw; OverviewTab missed the backend's lowercase `"critical"` risk level (fell through to green); NetworkTab injected mock peers when empty (removed — honest empty state). Backend root cause: `analyzer.py` never copied `behavioral_profile` into results (produced by the engine, silently dropped) — fixed; `report_generator.py` PDF psych key → `personality_traits`. `behavioral_profile` backfilled for tasks 6–12 from stored dossiers (one LLM call each, no re-scrape). `behavioral_analyzer` null-tolerance fixes (`profile: None`, `bio: None`).
- **Authenticity fabrication root cause (Nov 2026):** profile prompts read `followers_count` while dossiers store `follower_count` → model told "0 followers" while content said 2,061 → hallucinated "metric contradiction"; provider-unexposed `following`/`posts` arrived as placeholder 0s and were treated as real measurements → invented "purchased followers" narratives (old stored verdict: critical, bot 0.75). Fixed in `openrouter_client.analyze_authenticity` + `platform_prompts` (content + authenticity): keys normalized, unexposed metrics render as `unknown (not exposed by provider)`, explicit guardrail (never treat unknown as evidence; no claims about groups/multimedia/demographics without data). All stored `content_analysis` + `authenticity` sections regenerated from stored dossiers (tasks 6–12, no re-scrape): task 12 now **low / bot 0.15** with grounded flags. Tests: **63 passed / 0 failed**; `tsc && vite build` clean.
  **Hardening pass 2 (Nov 2026):** the first guardrail was still too weak — a fresh deep run (task 15) still produced "near-zero visible engagement", "no multimedia (video/Reels/Live)", "algorithmic suppression" and "male-dominated audience" even though the collector never captures engagement counts, media type, or demographics. Root cause: the prompts asserted *absence* of data streams as *absence on the account*. Both content and authenticity prompts now render an explicit `DATA BOUNDARIES` block computed from the actual samples (no media metadata / no engagement metrics / no group data / no demographic breakdowns) and forbid claims from missing streams; `Verified` also renders as `unknown` when the provider omits it. Regenerated task 15 → **medium / bot 0.15**, flags now limited to what the metrics show (account age, following, post count, unverified, numeric handle). **Belief analyzer:** the mandatory evidence block pushed output past the 6000-token cap, so content-rich profiles came back truncated (`JSON parse error`, e.g. tasks 8/9/15). `openrouter_client.analyze` now takes `max_tokens`, retries once on an empty completion, and re-requests once at double budget when a `JSONDecodeError` looks like truncation; belief analysis runs at 9000 tokens. Tasks 9 and 15 now return real compasses (Center-Left Libertarian-Leaning; Left-Conservative −5/−2 with 20 quoted samples, `evidence_quality: strong`). **No-data verdicts (Nov 2026):** when a run fetched neither profile metrics nor content, `analyze_authenticity` now short-circuits before the LLM and returns `risk_assessment: "unknown"`, `bot_likelihood: null` plus explicit `limitations` — previously it invented "high/critical bot risk" from an empty dataset (tasks 6/10/11). Callers pass `content_items` so the emptiness test uses the real dossier, not the model's prose; Overview tab renders Unknown instead of 0% and lists limitations separately from red flags.
  **Hardening pass 3 — deterministic grounding (Nov 2026):** prompt-level prohibitions alone were still leaky, so the guard is now enforced in code. `platform_prompts._content_availability` computes what a dossier actually contains (Facebook deep items *do* carry `reactionCount`/`share_count`/`commentCount` and `videoDetails`/`/reel/` URLs — the earlier hardcoded "no media, no engagement" text was itself wrong) and `_boundary_text` renders it into both prompts. After the model answers, `openrouter_client._filter_unbacked_flags` drops any red/green flag whose dimension was not collected (engagement, media, network, demographics, groups) or that asserts absence of something present ("no multimedia" while 11 reels exist); `_filter_unsupported_claims` applies the same test to `content_analysis.key_insights`. Removals are reported, never silent: `filtered_indicators` / `filtered_insights` plus a `limitations` line naming the missing dimension. "Political niche" is no longer an authenticity signal — topic is reported separately in `topical_focus` (`primary_topic`, `political_intensity`, verbatim `evidence`, `evidence_verified`) and every quote is checked against the collected post text; paraphrased quotes are dropped. Fresh deep run (task 16) → **medium / bot 0.15**, flags grounded, topic quoted verbatim. Also in this pass: `_request_json` centralises empty-completion retry + truncation re-request for content, authenticity and prediction calls, and the invented fallbacks are gone (authenticity no longer defaults to score 0.5; failed predictions return `null` growth instead of zeros that read as data). Beliefs tab now renders `EVIDENCE_AND_CALIBRATION` per axis (it was never displayed).
  **Longitudinal tracking + spend guard (Nov 2026):** Vanta can now track a subject over time instead of producing one-off reports. `DossierSnapshot` was a schema stub with zero rows and no writer; a snapshot (profile metrics, engagement arithmetic, post ids + publication window, verdicts) is now written on every successful run that collected something, and `GET /tasks/<id>/results` returns `history` (the subject's timeline, matched on resolved identity so handle-vs-numeric-id runs stay one history) plus `changes` (deltas vs the previous run). Deltas are computed in Python from stored snapshots, never asked of a model. Deletions are only reported when the two runs have comparable coverage (`comparable` + `coverage_note`); a 12-post run against a 40-post run reports "sampling, not deletion" instead of 28 vanished posts. Overview renders a History & changes panel. **Spend guard:** `record_credits` persists the last observed provider balance (`data/provider_usage.json`), `GET /provider/usage` reports balance and per-run cost, `/analyze` returns **402** before starting a run the balance cannot cover, and the nav shows the remaining runs. **Coverage receipts:** every result now carries `data_coverage` — per section, what it was computed from and whether it was measured at all — rendered as a strip above the tabs, so psych/consumer/lifestyle/network declare their inputs instead of appearing as findings. **Benchmark:** `evaluate_authenticity_benchmark` computes precision/recall/F1 for the authenticity verdict against labelled accounts and refuses to report accuracy below 20 labels; `data/benchmark/labels.json` is a 4-account seed with provenance per label and no invented "bot" examples. The set is **not yet scored** — that needs one run per account (~84 credits) and the balance was 4 when it was written. **DB path fix:** `sqlite:///relative` URIs were resolved by SQLAlchemy against Flask's `instance/` folder, so any process that loaded `.env` before the app factory pointed at `instance/data/...` and failed; relative paths are now anchored to the project root, and `.env` points at the database that actually holds the runs (`data/vanta.db`, not the stale `profilescope.db`).

  **Claim receipts (Nov 2026):** the psychology, consumer and lifestyle sections previously asserted traits and purchases with nothing behind them. Their prompts now require `evidence: [{claim, quote}]`, and `verify_claim_evidence` (in `platform_prompts.py`) checks every quote against the collected post text before the section is stored - a paraphrase is discarded exactly like an invention, the removals are counted in `evidence_rejected`, and the section records a limitation saying so. Results are rendered per tab as a receipts panel. Beliefs already worked this way; the other three now match it. Existing runs keep their old analyses: receipts are not invented for data that was never collected. **History chart:** the Overview panel plots engagement rate and bot likelihood across the subject's runs. **Benchmark citations:** `data/benchmark/labels.json` v2 adds a `sources` block (Meta CIB reports, EU DSA transparency database, Twibot-20, Botometer as a comparison baseline) with what each source gives and its limits, plus `harvest_rules`; `validate_benchmark_labels` drops any `is_inauthentic` row lacking a resolvable `source_ref` and a stated reason, and `evaluate_authenticity_benchmark` now withholds `accuracy` when the set contains no inauthentic account (it reports `false_positive_rate` instead) because an all-authentic set scores 100% while measuring nothing. **Erasure:** `DELETE /api/tasks/<id>` removes a run, its payload and its snapshot rows, owner-scoped, 409 while in flight - the first and only deletion path in the codebase. **Compliance:** `directives/CODEBASE_ASSESSMENT.md` §5 drafts the posture for special-category inference (lawful basis, tiered gating, retention targets, deletion gaps); it concludes the special-category sections should default to off.

  **Special-category gate (Nov 2026):** political/religious belief inference, intimate-relationship inference and substance-use inference now sit behind `privacy.allow_special_category_inference`, **default false**. With the gate closed the belief engine is not called at all and the behavioral prompt omits those schema fields, so the inference never happens; if a model volunteers them anyway they are replaced with an explicit `not_collected` notice. The UI shows "Not collected" with the reason instead of a blank or an innocent-looking "Unknown"/"NO" (which would itself be a claim). `ALLOW_SPECIAL_CATEGORY_INFERENCE=true` restores the sections. **Config actually loads now:** `get_config_path()` never looked at `config/config.json` (the documented location), so every config value in that file was silently ignored - including this flag. Fixed, with the project root resolved from the module path. **Retention:** `purge_expired_results` drops raw dossiers/posts after `raw_content_days` (30) and quoted evidence after `quote_receipt_days` (90), keeping snapshot rows and every computed metric, so history survives the purge. Runs daily via Celery beat (`purge_expired_data`, 03:17, `data` queue); windows configurable under `privacy.retention`. **Benchmark import:** `load_benchmark_csv` reads a cited dataset export, and rejects rows with an uncited or unresolvable `source_ref` - the same rule the JSON file follows. **Chart:** history now labels runs by date, falling back to an index when all runs share a date (as the backfilled ones do).

  **Neon Postgres (Nov 2026):** production database is now Neon project `silent-dew-45227430`, branch `production`, reached through the pooled endpoint for app traffic and the direct endpoint for migrations (`DATABASE_URL_UNPOOLED`). `.neon` pins the project (git-ignored). Three defects surfaced during the move and are fixed: (1) **the app factory never loaded `.env`**, so any process that imported it first read `DATABASE_URI` as unset and quietly used SQLite - two engines, two databases, which is exactly what happened mid-migration; `create_app` now loads `.env` before reading config. (2) **`app/web/database.py` built a second engine** with its own duplicated URI rules; URI normalisation (postgres alias, psycopg2 driver, mandatory SSL, relative SQLite anchoring) now lives in one helper used by both. (3) **migrations never created `dossier_snapshot` or `cross_platform_profile`** - only `db.create_all()` did, so a migration-built database had no history tables; new migration `bb4568e43fc8` adds them, and `create_all` is now skipped on Postgres so Alembic owns the schema (it previously created the tables and left `alembic_version` empty, making every migration fail with "type taskstatus already exists"). Existing SQLite data (9 users, 11 tasks, 6 snapshots, 4 posts, 6 claims, 6 verifications) was copied across. Auth stays on the app's own JWT implementation: sign-up/sign-in were verified against Neon, and the Neon Auth/Data API path was deliberately not adopted.

  **Render deployment (Nov 2026):** API is live at `https://vanta-api-9bqv.onrender.com` (service `vanta-api`, free plan, oregon) built from `main` with `pip install -r requirements.txt` and `gunicorn ... "app.web.app:create_app()"`. Env vars are set in Render (Neon pooled URI, SECRET_KEY, JWT_SECRET_KEY, OpenRouter, ScrapeCreators, Apify, NewsAPI, Google Fact Check, CORS_ORIGINS, `ALLOW_SPECIAL_CATEGORY_INFERENCE=false`). Verified live: `/api/health` reports a healthy database, unauthenticated calls get 401, task list returns the 9 Neon tasks, task 16 returns 6 snapshots + 7 measured coverage sections, and register→login→scoped task list works. **Procfile bug found by the first deploy:** the start command was unquoted, so bash read the parentheses in `create_app()` as a syntax error and exited 2 - it was broken for any Procfile host, not just Render. **Known limits of this deployment:** free instances sleep after ~15 idle minutes (cold start), 512 MB RAM, and background workers are not available on the free plan so `REDIS_URL` is intentionally unset and analysis runs on the in-process threading fallback; `data/provider_usage.json` is local machine state and is not deployed, so the credit pre-flight reports the balance as unknown (and unknown never blocks) until a run reports one from Render. **Free-plan only:** `render.yaml` (validated with Render's blueprint endpoint) declares just the web service and the `vanta-secrets` env group; the worker + Key Value block is commented out because workers return 402 without a card, and the free Key Value instance created during setup was deleted rather than left idling. **Quick-scan defect found by the first Render run (task 18):** `quick_scan` wrote posts to `recent_content` while every analyzer, the coverage builder and the report generator read `content`, so a quick run analysed and reported zero posts even when collection succeeded — it now writes `content` (older stored dossiers still read via a `recent_content` fallback) and uses the same Apify fallback as the deep path.

Not implemented in this repo: WebSockets, team/billing endpoints (`app/enterprise/*` modules exist but are **not** wired to any route), official SDKs.

## Known limits (not fabricated around)

- Facebook `following_count` / total `posts_count` are not exposed by the ScrapeCreators API → stay 0.
- Frontend is deployed on Vercel at **`https://vanta-intel.vercel.app`** (project `vanta-intel`, scope
  `fxinfo24s-projects`), built with `VITE_API_BASE_URL=https://vanta-api-9bqv.onrender.com/api`.
  `https://vanta.vercel.app` is **not available** — it is owned by an unrelated account, so neither a
  rename nor an alias can claim it. CORS pre-flight from the Vercel origin is verified against Render.
  `FRONTEND_URL` is set on Render so page requests to the API host (which serves no compiled UI)
  302 to the Vercel app; `/api/*` still answers normally. `https://profile-scope.vercel.app` is the
  older, duplicate Vercel project (root dir `frontend`, Dec 2025) still serving a stale build.
- **Dossier cache + spend guard made real (Nov 2026):** `dossier_cache` stores the last raw dossier
  per (user, platform, profile) with a TTL (`DOSSIER_CACHE_TTL_HOURS`, default 12), so re-analysis and
  regeneration reuse collected data instead of spending another 24 credits; empty dossiers are never
  cached, expired entries are purged by the retention job, and the coverage strip says when a run
  reused a cached dossier (with its collection time). The last observed provider balance now lives in
  `provider_credit_usage` (Postgres) rather than a JSON file beside the code — that file was invisible
  to any deployed instance, which is why the pre-flight guard saw "unknown" and let task 18 run into a
  402. A `CREDITS_EXHAUSTED` response now records a zero balance, so the next run is refused with 402
  before it starts instead of returning an empty dossier. Migration `f4c8d2e15b31` (applied to Neon).
- **Password reset (Nov 2026):** `POST /api/auth/forgot-password` mails a one-time link and
  `POST /api/auth/reset-password` redeems it. Only the SHA-256 hash of the token is stored
  (`password_reset_token`, migration `e3b7c1a94d20`, applied to Neon), links expire in 30 minutes,
  are single use, and issuing a new one retires the user's earlier links. The response never reveals
  whether an address has an account, and repeated requests are throttled silently. Delivery goes
  through Resend (or Brevo) — **with no key configured the endpoint answers 503** naming the missing
  variable rather than reporting a send that never happened. The UI has matching `/forgot-password`
  and `/reset-password` screens. **Delivery verified end to end (Nov 2026):** Resend reports
  `last_event: delivered` for the message, the link points at `https://vanta-intel.vercel.app/reset-password`,
  redeeming it returns 200, sign-in with the new password works, and replaying the same link returns 400.
  A failed send now revokes its token (`revoke_reset_token`) — it previously stayed in the table and
  counted against the 3-per-hour limit, which is what silently swallowed a later request.
- **Monitoring surface (Nov 2026):** every result with two or more snapshots now carries `alerts`
  and `not_evaluated` computed by `DossierSnapshot.compute_alerts` — followers drop (−3% / −10%),
  bot-likelihood jump (+0.2 or crossing 0.5), engagement drop (−30% with >= 5 measured posts),
  cadence drop (−50%), removed posts (>= 3 with comparable coverage), and display-name / badge /
  bio changes. Each alert names the rule, both numbers and the threshold, so a customer can
  recompute it from the stored snapshots; a rule whose inputs were not collected is listed as
  not evaluated instead of silently passing. Thresholds live under an optional `alerts` block in
  `config/config.json`. Overview renders the list with severity chips.
- **Feed dedupe + reels pagination (Nov 2026):** Facebook serves the same reel through the posts
  feed (numeric post id) and the reels feed (encoded id), so the dossier counted it twice — inflating
  `posts_measured`, which is the engagement denominator, and paying for its comments twice. Content
  is now merged and deduped by canonical URL keeping the richer copy (`statistics.duplicate_items_removed`),
  and the comment step skips an item it already requested. The reels endpoint also rejects a page-2
  request carrying `cursor` without `next_page_id`, which made every deep run log a 400 and stop at
  page one; both keys are now sent together (verified: 12 reels where 10 was the ceiling).
- **One implementation for engagement and cadence (Nov 2026):** `engagement_rate_percent` and
  `posting_cadence` live in `app/utils/helpers.py`; the LLM prompt, the content analyzer and the
  snapshot all call them, so the same profile cannot show 0.18% in one place and 0.2% in another
  (verified: 2.62 posts/week from both paths). A rate whose denominator is missing returns None.
- **Identity, not a suspicious handle (Nov 2026):** several platforms return the numeric user id in
  `username` when there is no vanity handle. The prompts printed only `@<username>`, so a real page
  was flagged for having a "numeric handle" while its name went unused. Both prompt builders now
  render `Display name` plus a handle line that labels a numeric id as a platform id and rules it out
  as evidence; the report header shows the name with the id beneath it; and flags asserting a numeric
  handle are dropped with the removal recorded (`filtered_indicators`). Flags about the provider
  omitting the verified badge move to `data_gaps` the same way (verified live: red_flags empty on
  "Arif Aziz", risk low, 0.15 bot likelihood).
- **Cache reaches CLI and desktop (Nov 2026):** a run with no signed-in user used to skip the dossier cache
  entirely, so re-analysing the same handle from the desktop paid the provider again. Those runs now
  share an operator-local scope (`DossierCache` owner `0`, distinct from every web user) backed by the
  same local database; a shared app is created once for the session. Unit tests install a barrier so an
  analyzer test without an app context can never read or write the developer's real database.
- **Progress reports stages, not a timer (Nov 2026):** a deep run used to sit at a frozen 10%
  "Processing" for its first eight minutes, and with no logs visible to the user a working run looked
  identical to a hung one. The collector now emits each finished step with its own counts ("collected
  posts (46 items)", "reading comments on 3 posts") and the bar moves only when a step completes, so a
  stall holds still instead of creeping. The single model pass owns 76–92% and its message says so —
  measured live at 606s for a cached run, i.e. the model call is the long pole and nothing else can be
  reported until it returns. A failing progress writer is logged and ignored: it can never take down a
  run that was already paid for.
- **Credit estimate corrected to measured cost (Nov 2026):** the guard priced a deep run at 14 credits
  while three funded runs cost 23, 24 and 24, so it would release a run with ~10 credits too few.
  `RUN_CREDIT_ESTIMATES["deep"]` is now 24. `quick` stays at the old conservative 4 because no quick
  run has been measured on the funded key — flagging it rather than replacing one guess with another.
- **A finished analysis is committed before its snapshot (Nov 2026):** the snapshot step rolls back on
  failure, and the result payload was still uncommitted at that point — a failed history write erased a
  completed analysis (task 21: status completed, no result, no error). The result now commits first, so a
  snapshot failure can only lose the snapshot. Verified after the fix: task 22 reused the cached dossier,
  stored its result and snapshot, and spent **0** of 1173 credits.
- **Absent badge is missing input (Nov 2026):** live runs kept listing "Not verified — no platform
  authenticity badge" as a red flag while "Account age unknown" was correctly a data gap. The gap test
  now recognises the phrasings models actually produce ("not verified", "no platform identity
  confirmation", "unavailable"). Verified on re-runs of `sahab0769`: task 25 still carried one
  "...unavailable — limits network-level validation" line, task 26 came back with `red_flags: []` and all
  four missing-input lines in `data_gaps`. Both re-runs reused the cached dossier and spent 0 credits.
- **One snapshot is not "no change" (Nov 2026):** with a single snapshot the results payload returned no
  `alerts` at all, which reads the same as a clean comparison. It now returns every rule as
  `not_evaluated` with the reason ("only one snapshot stored for this subject").
- **Freshness on the task list (Nov 2026):** `GET /api/tasks` carries `last_collected_at` (newest snapshot
  of that subject) and `history_depth` (how many snapshots exist), shown on the dashboard and task list so
  a report whose numbers are days old is not mistaken for a current one and one snapshot is not mistaken
  for a trend. Two grouped queries per page, not one per row.
- **A stored balance belongs to one key (Nov 2026):** the balance row now stores a truncated SHA-256
  of the provider key that produced it (migration `a7c9e14f2b83`, applied to Neon). After a key
  change the stored number describes an account no longer in use, so it is reported as inapplicable
  instead of rejecting every run with 402 — the deadlock that appeared when a stale zero from an
  exhausted key met a funded new key. A row with no fingerprint is treated the same way.
- Analysis is **funded again** (Nov 2026): the provider key was rotated and the recorded zero balance
  belonged to the old key, so it was reported as inapplicable (not blocking) — the exact deadlock the
  key fingerprint exists to prevent. Measured cost per deep run: **23–24 credits**. Runs verified with
  real data: `AzizMdArif` (2,061 followers, 49 posts, 1 duplicate removed, alerts fired: engagement
  −33.9%, 3 posts removed), `sahab0769` (আহমেদ সাহাব, 19,269 followers, 46 posts, 71 comments, 4
  duplicates removed), `faham.abdus` (Faham Abdus Salam, 535,033 followers, 50 posts, 97 comments).
  Balance 1173 → 1126 for the last two. **Render applies env-var changes only on a new deploy** — a
  `restart` keeps the old environment, which is why the rotated key looked ignored until a deploy ran.
  Earlier exhausted-key failures remain visible on task 18/19.
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
