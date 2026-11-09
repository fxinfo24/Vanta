# Agent Instructions

> No fakes, fabrications, or hallucinations. Don’t invent anything false. Base your responses on honest, real implementations, and don’t make me repeat the same warning repeatedly. Be brutally honest instead of acting like an impostor, fraud, or cheat. Maintain consistency with real implementations, enhancements, and updates. Be my real brutally honest sparring-partner.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

# AGENTS.md (Developer Guide)

## 📞 Session Resume Prompt (Vanta Special)

Copy this to start a new session:

```
I'm resuming work on the "Best in Class" social intelligence platform, Vanta (formerly Vanta). Please read HANDOVER.md and AGENTS.md immediately.

Current status:
- Infrastructure: Docker Compose (Full Stack - Verified Healthy)
- Branding: Fully rebranded to "Vanta" with premium logo.png and dark-mode UI.
- Capabilities: "Deep Mind" profiling implemented for TikTok (Comments), YouTube (Transcripts), and Instagram (Deep Posts).
- Backend: Python 3.14 + OpenRouter LLM (Nemotron default; no heuristic fallback — failures surface as errors). Product B (7-layer verification) consolidated into the same Flask app; see STATUS.md.
- Fixed: Resolved "Empty/Blank Results" bug, "Summary Generation Failed" error, Authenticity false positives, Input/Button lagging, Real-time Polling, Deep PDF Reports, and Mobile/Network Scalability.

My goal: [describe what you want to do]
```

## 🌌 The Vanta Evolution (Best in Class)

Vanta has evolved into **Vanta**—the industry's most advanced social intelligence platform.

### 🌌 Vanta Design Language
- **Brand**: Vanta (Total data absorption, stealth intelligence).
- **Aesthetics**: Premium Glassmorphism, Deep Dark Mode (#020617 background), Vibrant Cyan/Indigo accents.
- **Logo**: Futuro-Vortex `/logo.png` representing the ingestion of global social datasets.

---

## You must follow ALL of these principles:

1. Practice systematic problem solving

- Do not apply random or trial-and-error fixes.
- Work from first principles: understand the problem, form a hypothesis, verify it, then implement a targeted solution.
- Always explain your reasoning and the steps you take.

2. Report status honestly

- Do not claim a problem is solved until it is fully verified.
- Clearly state what is:- Confirmed working
- Still under investigation
- Not yet tested

- If you are unsure, say so explicitly.

3. Perform true root cause analysis

- Do not only treat visible symptoms.
- Identify the actual root cause and explain it clearly.
- Show how the fix addresses that root cause, not just the immediate error or side effect.

4. Make solutions permanent, proper, and robust

- Implement fixes that are stable, maintainable, and resilient to edge cases.
- Remove or refactor fragile workarounds when possible.
- After changing the behavior, update all affected:- Scripts
- Configuration
- Code comments
- Documentation or readme instructions
- If you find duplicate, outdated, unused, or confusing files, merge into the best version and safely remove the rest. Update related docs.

- Ensure the codebase remains consistent and coherent after your changes.

5. Do NOT create any new files under any circumstances

- Absolutely no new files: no new source files, scripts, configs, docs, or assets.
- Start with a thorough search of the existing codebase. Inspect all relevant modules, scripts, and docs.
- Use and refine existing files and scripts. If something is missing, integrate it into an appropriate existing file instead of creating a new one.
  (AI assistants in general have a tendency to create new files as the "easy" solution without properly investigating what already exists. This leads to:

1. Codebase bloat – Multiple files doing similar things
2. Maintenance nightmares – Updates needed in multiple places
3. Developer confusion – “Which file should I modify?”
4. Technical debt – Eventually requiring cleanup/consolidation work)

(The "no new
files" principle should apply to
source code, not to data artifacts.
Data files are expected outputs of
ML workflows.)

General behavior requirements:

- Begin by performing an exhaustive search in the existing repository for relevant code, scripts, configurations, and documentation before proposing a fix.
- Prefer minimal, targeted changes that maximize clarity and maintainability.
- When you propose changes, reference specific files, functions, and locations (e.g., line numbers or search markers) where possible.
- After designing a fix, describe:- What you changed
- Why you changed it
- How it solves the root cause
- How to test and verify it works

You must comply with all of the above at every step.

You should challenge my ideas and suggest alternatives instead of just agreeing.

Here’s how I want you to respond:

- Critically evaluate my requests and consider if there’s a better way.
- Offer alternative approaches and clearly explain the trade-offs.
- Question my assumptions and ask why I want to do something a certain way.
- Provide expert guidance based on best practices, not just my initial suggestion.

## Project overview

- **Name**: Vanta
- **Purpose**: AI-powered social media profile intelligence/analysis across 10+ platforms.
- **Primary language**: Python
- **Key backend frameworks/libraries**:
  - Flask + SQLAlchemy (`app/web/`)
  - Celery + Redis for background jobs (`app/core/tasks.py` - canonical config)
  - NLP/ML stack: `nltk`, `spacy`, `transformers`, `torch`
  - Scraping/API integrations: ScrapeCreators client (`app/core/scrape_client.py`) and legacy platform APIs
  - LLM integration: OpenRouter (`app/core/openrouter_client.py`)
  - Desktop GUI: PyQt (`app/desktop/`)
- **Frontend**:
  - React + TypeScript + Vite (`frontend/`)
  - Mobile: React Native + Expo (`mobile/`)

## Quick start (backend)

- Create & activate a virtualenv:
  - `python -m venv venv`
  - `source venv/bin/activate`
- Install Python dependencies:
  - Local development (all features): `pip install -r requirements-full.txt`
  - Railway/production (minimal): `pip install -r requirements.txt` (auto-detected)
- Configure environment:
  - `cp .env.example .env`
  - Fill in required API keys (see **Environment & config** below)
- Download NLTK resources (commonly required by tests/analysis):
  - `python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('vader_lexicon')"`

## How to run

### Main entry point

- Use `bin/run.py` as the main launcher:
  - Web: `python3 bin/run.py --web`
  - Desktop: `python3 bin/run.py --desktop`
- Convenience scripts:
  - Web: `bash bin/start_web.sh`
  - Desktop: `bash bin/start_desktop.sh`

> Note: Some docs still mention `python run.py ...` from an earlier layout. In this repo, the entry point is `bin/run.py`.

### Web app (Flask)

- App factory (current): `app/web/app.py:create_app(test_config=None)`
- Typical URL: `http://127.0.0.1:5000`
- SQLite is used by default in development; the app ensures `data/` exists and creates `data/vanta.db`.

### Desktop app (PyQt)

- Main module: `app/desktop/app.py` (`main()`)
- If you hit GUI/ML dependency issues on some platforms, try:
  - Safe mode launcher: `bash scripts/start_desktop_safe.sh`
  - Minimal mode (Tkinter): `bash scripts/start_desktop_minimal.sh`

### Real-time processing (Celery + Redis)

- Start Redis, then:
  - `bash scripts/start_celery.sh`
- Flower monitoring dashboard:
  - `http://localhost:5555`
- Queues commonly used:
  - `analysis`, `vision`, `reports`, `data`

## Frontend (React + Vite)

- Location: `frontend/`
- Dev server (proxies `/api` to Flask on port 5000):
  - `cd frontend && npm install && npm run dev`
- Build output:
  - Vite builds into `app/web/static/dist` (see `frontend/vite.config.ts`).

## Mobile (Expo)

- Location: `mobile/`
- Run:
  - `cd mobile && npm install && npx expo start`

## Tests

- Pytest config: `config/pytest.ini`
- Run tests (inside the project virtualenv, after `pip install -r requirements-full.txt`):
  - `python -m pytest`
  - or `python3 bin/run_tests.py`
    - `--simple` runs a minimal verification test
    - `--html-report` optionally generates an HTML report (requires `pytest-html`)

> Note: `bin/run_tests.py` runs the repository cleanup script at `scripts/cleanup.sh` before tests (unless `--skip-cleanup`).

## Database migrations (production)

- Migrations are managed by Alembic/Flask-Migrate (`migrations/`).
- For production (Railway/Postgres), prefer migrations over `db.create_all()`.
- Typical flow:
  - `export FLASK_APP=app.web.app`
  - `flask db upgrade`

## Deployment (recommended)

- **Frontend (Vercel)**
  - Set `VITE_API_BASE_URL` to your backend base URL (e.g., `https://your-backend.com/api`)
- **Backend** (choose one):
  - **Render.com** (recommended, free tier): `gunicorn -b 0.0.0.0:$PORT app.web.app:create_app()`
  - **Fly.io** (free tier): Use `fly launch` and `fly deploy`
  - **Railway** (paid): Auto-deploys from GitHub
  - **Local**: `python3 bin/run.py --web`
- See `directives/HANDOVER.md` for detailed deployment instructions and current project state.

## Postgres results storage notes

- Task results are stored in `Task.result_data` as **JSONB** on Postgres.
- `Task.result_data` is **deferred** by default to keep list queries fast.
- Indexes exist on `(status, created_at)` and `(platform, created_at)` for dashboard/list endpoints.

## Environment & config

- `.env.example` contains the canonical environment variables to copy into `.env`.
- Common environment variables:
  - `FLASK_HOST`, `FLASK_PORT`, `FLASK_DEBUG`
  - `DATABASE_URI` (defaults to SQLite; `DATABASE_URL` is accepted as the managed-Postgres convention)
  - Use the **pooled** endpoint for app traffic, the **direct** one (`DATABASE_URL_UNPOOLED`) for `flask db upgrade`
  - On Postgres, Alembic owns the schema: `create_all()` is skipped, so a new table needs a migration
  - API keys (legacy): `TWITTER_*`, `FACEBOOK_*`
- JSON config:
  - `config/config.json` contains app defaults (logging, output locations, analysis settings).
  - `PROFILESCOPE_CONFIG` environment variable can override the config path (see `app/utils/config.py`).

## Important directories

- `app/core/`: analysis engine and integrations
  - `analyzer.py`: `SocialMediaAnalyzer`
  - `data_collector.py`: `DataCollector`
  - `content_analyzer.py`: `ContentAnalyzer`
  - `authenticity.py`: profile authenticity scoring
  - `prediction.py`: `PredictionEngine`
  - `tasks.py`: Celery tasks
  - `openrouter_client.py`: LLM analysis client
  - `scrape_client.py`: unified scraping/data collection client
- `app/web/`: Flask app (routes, templates, models)
  - `routes/api.py`, `routes/views.py`
  - `templates/`, `static/`
- `app/desktop/`: desktop GUI and views/widgets
- `app/utils/`: shared utilities (config, logging, NLP helpers)
- `config/`: runtime config, pytest config, celery config
- `scripts/`: operational scripts (Celery, cleanup, env setup)
- `tests/`: unit/integration tests
- `data/`: local database, results, and other generated artifacts
- `logs/`: log output (created/used by cleanup and web logging)

## Conventions & best practices (observed)

- Prefer **app factories** for Flask (`create_app`) and initialize extensions inside the factory.
- Prefer **configuration via `.env` and `config/config.json`** rather than hardcoding secrets.
- Keep generated outputs in `data/`, `results/`, and `logs/` (don’t commit generated artifacts).
- When adding new Celery tasks:
  - Put them in `app/core/tasks.py`.
  - Add routing/queue mapping in the `celery_app.conf.update()` section of `app/core/tasks.py` (lines 40-51).
- Frontend API calls should target `/api/*` so Vite’s proxy works in development.

## Where to look first when debugging

- Web startup/config issues:
  - `app/web/app.py`
  - `app/web/models.py`, `app/web/database.py`
  - logs: `logs/vanta_web.log` and `data/logs/vanta.log`
- Analysis logic:
  - `app/core/analyzer.py`, `app/core/content_analyzer.py`, `app/core/authenticity.py`
- Task processing:
  - `app/core/tasks.py` (Celery configuration), Redis connectivity

## Documentation index

- `directives/CODEBASE_ASSESSMENT.md`: strategic analysis & roadmap
- `directives/setup_guide.md`: setup & API keys
- `directives/development.md`: dev workflows and architecture
- `directives/api.md`: API overview
- `directives/desktop_mobile.md`: desktop/mobile notes
