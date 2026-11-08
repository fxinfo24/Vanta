# Vanta (formerly Vanta) - Session Handover Document

> **Last Updated**: November 2026
> **Purpose**: Complete context for resuming work in a new session. **Current verified state lives in `STATUS.md` (repo root) — read that first; this file is session context only.**

---

## 📋 Project Summary

**Vanta** is a social intelligence platform providing deep AI analysis across **21+ platforms** via a "Deep Mind" dossier engine (`SocialMediaAnalyzer` → `DeepDossierCollector` → intelligence analyzers → OpenRouter). Default LLM model is **Nemotron** (`nvidia/nemotron-3-ultra-550b-a55b:free`, override via `OPENROUTER_MODEL`). There is **no heuristic fallback** — if the LLM call fails, the section stores an error. Product B (7-layer verification) is consolidated into the same Flask app + DB (see `STATUS.md`).

### Tech Stack (Upgraded)
| Layer | Technology | Status |
|-------|------------|--------|
| **Frontend** | React 18 + TypeScript + Vite | ✅ Containerized (Docker) |
| **Backend** | Python 3.14 + Flask + Celery | ✅ Containerized (Docker) |
| **Intelligence** | OpenRouter LLM (Nemotron default) + Apify fallback for scraping | ✅ Verified live |
| **Data** | Universal ScrapeCreators (20+ Platforms) | ✅ Configured for all platforms |
| **Infra** | Docker Compose (Full Stack) | ✅ **READY FOR DEPLOYMENT** |

---

## 🎨 Current State

### Universal Connectivity - ✅ SOLVED
The entire stack is now containerized and orchestrated via Docker Compose. No more manual terminal juggling.
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000
- **Task Monitor**: http://localhost:5555 (Flower)

### Platform Capabilities
| Category | Supported Platforms |
| :--- | :--- |
| **Social** | Twitter/X, Facebook, Instagram, Reddit, Snapchat, Pinterest |
| **Video** | TikTok, YouTube, Twitch, Kick |
| **Professional** | LinkedIn, GitHub, Threads, BlueSky |
| **Commerce** | **TikTok Shop, Amazon Shop**, Google, Linktree |
| **Intelligence** | Bot Detection, Deepfake Analysis, Commerce Conversion Metrics |

---

## 📂 Project Structure (Docker Optimized)

```
Vanta/
├── app/
│   ├── core/           # Hybrid Intelligence Engine
│   │   ├── analyzer.py         # Universal Orchestrator
│   │   ├── openrouter_client.py # AI Client (Nemotron default)
│   │   ├── scrape_client.py    # Universal Data Adapter (20+ Platforms)
│   │   └── ...
│   ├── web/            # Flask API
│   └── ...
├── frontend/           # React + TypeScript
│   ├── Dockerfile      # Frontend container config
│   └── ...
├── docker-compose.yml  # Full stack orchestration (API, Worker, Frontend, Redis)
├── Dockerfile          # Backend/Worker container config
├── requirements-full.txt # Python dependencies (venv is 3.14)
└── ...
```

---

## 🔧 Immediate Next Steps

### Priority 1: Run with Docker (Recommended)
This is the single source of truth for running the application.

```bash
# 1. Start the entire platform
docker compose up -d --build

# 2. Monitor logs (optional)
docker compose logs -f
```

### Priority 2: Verify Intelligence
Once running:
1. Go to http://localhost:5173
2. Enter a username (e.g., `elonmusk` for Twitter or a product handle for Amazon)
3. The system calls OpenRouter (Nemotron). If the LLM is unavailable, the affected section records an error (no heuristic fallback).

---

## 🎯 Completed Work This Session

| Task | Status |
|------|--------|
| **Vanta Rebrand** | ✅ Fully implemented (Logo, Favicon, UI, Naming) |
| **Deep Mind Intelligence** | ✅ Added TikTok, YouTube, Instagram (Deep Posts) |
| **Intelligence Engine** | ✅ OpenRouter LLM (no heuristic fallback) |
| **Universal Platform Support** | ✅ Added Google, Linktree, Komi, Pillar, Linkbio, Shops (21+ Total) |
| **Fixed Analysis Failures** | ✅ Solved "Summary generation failed" & Authenticity false positives |
| **Docker Orchestration** | ✅ Full Stack Healthy (Clean Redeploy) |
| **Premium UI** | ✅ Added **Network Graph** & Deep Dossier Visualization |
| **Main Bug Fixes** | ✅ Fixed PDF Dossier 500 Errors, JSON Parsing, Mobile Scaling |
| **Mobile Optimization** | ✅ Responsive Header, Tabs, Forms, & Network Graph Scaling |

---

## 🎨 Rebrand Proposal: "Vanta"

*   **Name**: **Vanta** (derived from Vantablack - absorbing all light/data; seeing into the unknown).
*   **Concept**: Sleek, dark-mode first, "Black Box" intelligence revealed.
*   **Logo**: Abstract vortex/eye (generated in artifacts).

---

## 🔑 API Keys Location

All API keys are in `.env` file. The Docker containers automatically load these.
- `OPENROUTER_API_KEY`: Required for LLM analysis.
- `SCRAPECREATORS_API_KEY`: Required for real data (system mocks if missing). Balance is dashboard-only (no credits API).
- `APIFY_API_TOKEN`: Optional fallback scraper (Facebook). Free-tier usage is currently exhausted — raise the limit at console.apify.com/billing to activate the fallback.

---

## 📞 Session Resume Prompt (Vanta Standard)

Copy this to start a new session to ensure NO confusion:

```
I'm resuming work on **Vanta** (formerly ProfileScope).
This is a Vanta Deep Intelligence System session.

CRITICAL:
1. The Repo URL is now: https://github.com/fxinfo24/Vanta.git
2. Read `directives/HANDOVER.md` and `AGENTS.md` immediately for context.
3. The system runs via Docker Compose (`docker compose up -d`).

Current State:
- Architecture: Dockerized Full-Stack (Flask + React + Redis).
- Core: Deep Intelligence Engine with Self-Healing Identity Resolution.
- Status: Fully operational (Deep Analysis, Network Graphs, Dossier Downloads verified).
- Tech Stack: Python 3.14, Flask, React TypeScript, SQLite (Dev).

Goal: Continue enhancing the Vanta platform.
```

---

**End of Handover Document**
