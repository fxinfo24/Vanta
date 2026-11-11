```text
██╗   ██╗ █████╗ ███╗   ██╗████████╗ █████╗ 
██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██╔══██╗
██║   ██║███████║██╔██╗ ██║   ██║   ███████║
╚██╗ ██╔╝██╔══██║██║╚██╗██║   ██║   ██╔══██║
 ╚████╔╝ ██║  ██║██║ ╚████║   ██║   ██║  ██║
  ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
```

# Vanta

Vanta is an AI-powered social media intelligence platform: profile analysis across 21 platforms (Twitter/X, Instagram, LinkedIn, TikTok, Facebook, YouTube, Snapchat, Pinterest, Reddit, GitHub, commerce channels, …) plus a consolidated 7-layer claim-verification pipeline in the same Flask app.

**Current verified state:** see `STATUS.md` (single source of truth). Data via ScrapeCreators (primary) with Apify fallback; LLM analysis via OpenRouter (Nemotron). No auth on the API, no enterprise/team endpoints wired — `app/enterprise/*` modules exist but are not exposed via routes.

## Features

### 🌍 Universal Platform Coverage
- **20+ Platforms Supported**:
  - **Social**: Twitter/X, Facebook, Instagram, Reddit, Snapchat, Pinterest
  - **Video**: TikTok, YouTube, Twitch, Kick
  - **Professional**: LinkedIn, GitHub, Threads, BlueSky
  - **Commerce**: Amazon Shop, TikTok Shop, Google Shopping, Linktree
- **Intelligence**: OpenRouter LLM analysis (default `nvidia/nemotron-3-ultra-550b-a55b:free`, override with `OPENROUTER_MODEL`). If the LLM call fails, the section records an error — there is no heuristic fallback.
  - **Data**: ScrapeCreators unified adapter (primary) → Apify actor fallback on credit exhaustion (Facebook).

## Quick Start (Docker)

The fastest way to run Vanta is via Docker Compose:

```bash
# Start the full stack (Frontend + Backend + AI + Database)
docker compose up -d --build
```

Access the application:
- **Web App**: http://localhost:5173
- **API**: http://localhost:5000/api/health
- **Task Monitor**: http://localhost:5555

## Manual Installation

If you prefer running without Docker:
1. **Python 3.13+** is required.
2. Install dependencies:
```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements-full.txt
```

```bash
# Local development (recommended):
pip install -r requirements-full.txt

# Railway will auto-detect requirements.txt (minimal, fast builds)
```

4. Setup NLP components:
```bash
# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('vader_lexicon')"
```

5. Configure API credentials:
- Copy `.env.example` to `.env`
- Fill in your Twitter/Facebook API credentials
- See `docs/setup_guide.md` for detailed setup instructions

## Usage

### Command Line Interface

Analyze a profile:
```bash
# Main launcher (this repo uses bin/run.py)
python3 bin/run.py --web
# or
python3 bin/run.py --desktop
```

Options (launcher):
- `--web`: run the Flask web app
- `--desktop`: run the desktop app
- `--host`, `--port`, `--debug`: web server options

### Real-time Processing
Start the Celery workers for background processing:
```bash
# Start real-time processing pipeline
scripts/start_celery.sh

# Monitor tasks at http://localhost:5555 (Flower dashboard)
```

### Mobile Application
Build and run mobile apps:
```bash
cd mobile
npm install
npx expo start

# For iOS: npx expo start --ios
# For Android: npx expo start --android
```

### Desktop Application

Launch the desktop GUI:
```bash
python -m app.desktop.app
```

### Web Interface

Start the web server:
```bash
python3 bin/run.py --web
```

### Database migrations (production)

This repo includes Alembic/Flask-Migrate in `migrations/`.

- In development/testing, the app may use `db.create_all()`.
- In production (Railway/Postgres), run migrations instead (e.g., as a Railway **Release Command**):

```bash
export DATABASE_URI="postgresql://..."
export FLASK_APP=app.web.app
flask db upgrade
```

## Production Deployment

### Architecture Overview

Vanta uses a **split deployment**:
- **Frontend**: Vercel (React/TypeScript static site)
- **Backend**: Any Python-capable hosting (Flask API)

### Backend Hosting Options

Choose ONE of the following options for hosting the Flask backend:

#### Option A: Render.com (Recommended - Free Tier Available)

1. **Create Account**: Go to https://render.com and sign up
2. **New Web Service**: Connect your GitHub repository
3. **Configure Build**:
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn -b 0.0.0.0:$PORT app.web.app:create_app()
   ```
4. **Environment Variables**:
   ```bash
   SECRET_KEY=your-secure-random-key
   CORS_ORIGINS=https://profile-scope.vercel.app
   OPENROUTER_API_KEY=your-openrouter-key
   SCRAPECREATORS_API_KEY=your-scrapecreators-key
   DATABASE_URI=sqlite:///data/vanta.db
   ```
5. **Deploy** and note your backend URL

#### Option B: Fly.io (Free Tier Available)

1. **Install CLI**: `brew install flyctl` (or see https://fly.io/docs/hands-on/install-flyctl/)
2. **Login**: `fly auth login`
3. **Launch**: `fly launch` in project root
4. **Set Secrets**:
   ```bash
   fly secrets set SECRET_KEY=your-secure-key
   fly secrets set CORS_ORIGINS=https://profile-scope.vercel.app
   fly secrets set OPENROUTER_API_KEY=your-key
   fly secrets set SCRAPECREATORS_API_KEY=your-key
   ```
5. **Deploy**: `fly deploy`

#### Option C: Railway (Paid - $5/month)

1. **Create Project**: Go to https://railway.app
2. **Connect GitHub**: Link your repository
3. **Add Services**: PostgreSQL and Redis (optional)
4. **Configure Environment Variables** (same as above)
5. **Deploy**: Railway auto-deploys from main branch

#### Option D: Local Development

```bash
# Backend (Terminal 1)
source venv/bin/activate
python3 bin/run.py --web
# Runs on http://localhost:5000

# Frontend (Terminal 2)
cd frontend && npm run dev
# Runs on http://localhost:5173
```

### Frontend Setup (Vercel)

1. **Connect Repository**: Import `fxinfo24/Vanta` to Vercel
2. **Configure**:
   - Framework: Vite
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
3. **Environment Variables**:
   ```bash
   VITE_API_BASE_URL=https://your-backend-url.com/api
   ```
4. **Deploy**: Auto-deploys on push to main

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask secret key for sessions |
| `CORS_ORIGINS` | Yes | Comma-separated frontend URLs |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API for LLM analysis (Nemotron default) |
| `SCRAPECREATORS_API_KEY` | Yes | ScrapeCreators API for social data |
| `APIFY_API_TOKEN` | No | Apify fallback scraper (Facebook); free tier = $5/month usage credit |
| `DATABASE_URI` | No | PostgreSQL URL (defaults to SQLite) |
| `REDIS_URL` | No | For Celery background tasks |
| `FORCE_CELERY` | No | Set to "true" to use Celery over threading |
| `QSTASH_TOKEN` | No | Upstash QStash: durable verification jobs, no worker process (free 1,000 msgs/day) |
| `QSTASH_CURRENT_SIGNING_KEY` | No | Required with `QSTASH_TOKEN` to verify QStash deliveries |
| `QSTASH_NEXT_SIGNING_KEY` | No | QStash key rotation |
| `QSTASH_URL` | No | Regional QStash endpoint (e.g. `https://qstash-us-east-1.upstash.io`) |
| `PUBLIC_API_BASE_URL` | No | Externally reachable API base for signed QStash destinations |

### Verify Deployment

```bash
# Test backend health
curl https://your-backend.com/api/stats/completion-rate

# Test CORS
curl -I https://your-backend.com/api/tasks \
  -H "Origin: https://profile-scope.vercel.app"

# Create analysis
curl -X POST https://your-backend.com/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"platform":"twitter","profile_id":"elonmusk"}'
```

### Troubleshooting

**CORS Issues**
- Ensure `CORS_ORIGINS` includes your exact Vercel URL
- No trailing slashes in URLs
- Check browser console for specific errors

**API Errors**
- Verify `OPENROUTER_API_KEY` is set correctly
- Check backend logs for detailed error messages

For detailed setup instructions, see `directives/setup_guide.md`.

### Results storage (production)

- Task results are persisted in the database in `task.result_data` (Postgres JSONB).
- The `task.result_data` column is **deferred** by default to keep task listing fast.
- `/api/tasks/<id>/results` and `/api/tasks/<id>/download` serve results from the DB.
### Shortcut for Both

```bash
python3 bin/run.py --desktop  # Desktop app
python3 bin/run.py --web      # Web interface
```

Access the web interface at `http://localhost:5000`

## Development

### Project Structure

- `app/core/`: Core analysis engine with universal API integration
- `app/desktop/`: Desktop GUI application (PyQt5)
- `app/web/`: Web application (Flask + React TypeScript frontend)
- `app/enterprise/`: Team management and white-label features
- `app/utils/`: Utility functions and helpers
- `frontend/`: React + TypeScript web interface
- `mobile/`: React Native + Expo mobile applications
- `tests/`: Comprehensive test suites
- `data/`: Data storage and results
- `docs/`: Complete documentation including transformational achievements
- `scripts/`: Deployment and management scripts

### Running Tests

Run tests inside the project virtualenv after installing dependencies:

```bash
python3 bin/run_tests.py --simple
python3 bin/run_tests.py
# or
python -m pytest
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all contributors
- Built with Python and modern data analysis libraries
- Powered by machine learning and NLP technologies

## Documentation

### Directives (SOPs)
- **Codebase Assessment**: `directives/CODEBASE_ASSESSMENT.md` - Strategic analysis and roadmap
- **Setup Guide**: `directives/setup_guide.md` - Installation, API configuration, and verification
- **API Documentation**: `directives/api.md` - Complete REST API reference
- **Development Guide**: `directives/development.md` - Developer setup and contribution guide  
- **Desktop & Mobile**: `directives/desktop_mobile.md` - Desktop and mobile application documentation
- **Session Handover**: `directives/HANDOVER.md` - Project state and deployment options
- **Agent Guide**: `AGENTS.md` - Core operating principles and architecture

## Status

See `STATUS.md` for the current verified state, known limits, and docs map. In short: local stack (Flask :5000 + Vite :5173) is fully working E2E; the Vercel frontend needs a deployed backend URL via `VITE_API_BASE_URL`; no auth, no team/billing endpoints (enterprise modules unwired).

## Support

For support, please:
1. Check the comprehensive documentation in the `directives/` directory
2. Review `AGENTS.md` for core operating principles
3. Open an issue on GitHub with detailed information
4. Contact the development team for enterprise inquiries
