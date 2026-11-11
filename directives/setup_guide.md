# Vanta Setup Guide

## Quick Start

### 1. Environment Setup
```bash
# Ensure Python 3.12+ is installed
python3 --version

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-full.txt  # For local development
# OR: pip install -r requirements.txt  # For Railway production (minimal)
```

### 2. Universal API Configuration

#### ScrapeCreators Setup (Primary - 10+ Platforms)
Vanta uses ScrapeCreators for universal access to 10+ social media platforms:

1. **Configuration Required**: Add your ScrapeCreators API key to .env file
2. **Supported Platforms**: Twitter/X, Instagram, LinkedIn, TikTok, Facebook, YouTube, Snapchat, Pinterest, Reddit, GitHub
3. **Setup Instructions**: 
   ```
   # Copy .env.example to .env and add your API key
   SCRAPECREATORS_API_KEY=your_scrapecreators_api_key_here
   SCRAPECREATORS_BASE_URL=https://api.scrapecreators.com
   ```

#### OpenRouter AI Setup (Universal AI Access)
Vanta uses OpenRouter for access to multiple AI models:

1. **Configuration Required**: Add your OpenRouter API key to .env file
2. **Default model**: `nvidia/nemotron-3-ultra-550b-a55b:free` (verified live). Override with `OPENROUTER_MODEL` (e.g. `nvidia/nemotron-3.5-super-vl:free`).
3. **Setup Instructions**:
   ```
   # Add your OpenRouter API key to .env file
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

#### Apify Setup (fallback scraper, optional)
Used automatically when ScrapeCreators credits exhaust (Facebook). Actor: `apify/facebook-posts-scraper`.
```
APIFY_API_TOKEN=your_apify_token_here
```
Note: the free plan includes $5 of usage per monthly cycle (hard cap, `maxMonthlyUsageUsd`), which covers
roughly a few dozen Facebook profile runs — raise the limit at https://console.apify.com/billing if the
fallback returns 402. Check what is left with `GET https://api.apify.com/v2/users/me/usage/monthly`.

#### Legacy Individual APIs (Optional)
For direct API access (not recommended - use ScrapeCreators instead):
- Twitter Developer Portal: https://developer.twitter.com/
- Facebook for Developers: https://developers.facebook.com/

### 3. Verify Installation
```bash
# Test core functionality with universal APIs
python -c "from app.core.scrape_client import get_scrape_client; from app.core.openrouter_client import openrouter_client; print('✅ Universal APIs ready')"

# Start web interface (Flask)
python3 bin/run.py --web

# Start desktop interface
python3 bin/run.py --desktop

# Start real-time processing
scripts/start_celery.sh

# Start mobile development
cd mobile && npx expo start

# Build frontend
cd frontend && npm run build
```

## Architecture Overview

### Fixed Issues
The following critical issues have been resolved:

1. **Circular Import Dependencies**: Removed Flask initialization from core package
2. **Database Integration**: Fixed SQLAlchemy model imports
3. **Missing Dependencies**: Installed all required packages with fallbacks
4. **API Client Issues**: Added graceful handling for optional packages

### Current Status
- ✅ **Web Interface**: React + TypeScript at http://127.0.0.1:5000
- ✅ **Mobile Applications**: React Native + Expo (iOS/Android)
- ✅ **Desktop Application**: PyQt5 GUI with advanced visualizations
- ✅ **10+ Platform Support**: Universal data collection via ScrapeCreators
- ✅ **Universal AI**: Nemotron (default free model) via OpenRouter, override with `OPENROUTER_MODEL`
- ✅ **Real-time Processing**: Celery + Redis with Flower monitoring
- ✅ **Enterprise Features**: Team management and white-label ready
- ✅ **Database**: PostgreSQL (production), SQLite (development)
- ✅ **Computer Vision**: OpenCV-based image analysis

### Component Architecture
```
Vanta/
├── app/
│   ├── core/           # Universal API integration & analysis engine
│   ├── web/            # Flask API + database models
│   ├── desktop/        # PyQt5 GUI application
│   ├── enterprise/     # Team management & white-label features
│   └── utils/          # Shared utilities and helpers
├── frontend/           # React + TypeScript web interface
├── mobile/             # React Native + Expo mobile apps
├── data/               # Data storage and results
├── tests/              # Comprehensive test suites
├── docs/               # Complete documentation
└── scripts/            # Deployment and management scripts
```

## Testing

### Automated Tests
```bash
# Run all tests
python3 bin/run_tests.py

# Run specific test categories
pytest tests/test_core/
pytest tests/test_web/
pytest tests/test_utils/
```

### Manual Testing
```bash
# Test web API (tasks)
curl -X POST http://127.0.0.1:5000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"platform":"twitter","profile_id":"elonmusk"}'

# List tasks
curl http://127.0.0.1:5000/api/tasks
```

## Production Deployment

### Backend Hosting Options

Choose ONE of the following options for hosting the Flask backend:

#### Option A: Render.com (Recommended - Free Tier)

1. Go to https://render.com and create an account
2. Create a new "Web Service" and connect your GitHub repository
3. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -b 0.0.0.0:$PORT app.web.app:create_app()`
4. Add environment variables:
   ```bash
   SECRET_KEY=your-secure-random-key
   CORS_ORIGINS=https://profile-scope.vercel.app
   OPENROUTER_API_KEY=your-openrouter-key
   SCRAPECREATORS_API_KEY=your-scrapecreators-key
   DATABASE_URI=sqlite:///data/vanta.db
   ```
5. Deploy and note your backend URL

#### Option B: Fly.io (Free Tier)

1. Install CLI: `brew install flyctl`
2. Login: `fly auth login`
3. Launch: `fly launch` in project root
4. Set secrets:
   ```bash
   fly secrets set SECRET_KEY=your-secure-key
   fly secrets set CORS_ORIGINS=https://profile-scope.vercel.app
   fly secrets set OPENROUTER_API_KEY=your-key
   fly secrets set SCRAPECREATORS_API_KEY=your-key
   ```
5. Deploy: `fly deploy`

#### Option C: Railway (Paid - $5/month)

1. Go to https://railway.app and create a project
2. Connect your GitHub repository
3. Add PostgreSQL and Redis add-ons (optional)
4. Configure environment variables
5. Deploy (auto-deploys from main branch)

#### Option D: Local Development

```bash
# Backend (Terminal 1)
source venv/bin/activate
python3 bin/run.py --web

# Frontend (Terminal 2)
cd frontend && npm run dev
```

### Frontend Setup (Vercel)

Set `VITE_API_BASE_URL` to your backend URL + `/api`, e.g.:
`https://your-backend.onrender.com/api`

### Database Setup
```bash
# Run migrations (recommended for production)
export FLASK_APP=app.web.app
flask db upgrade
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Missing NLTK Data**: Run the NLTK download commands in the setup
3. **API Errors**: Check your API credentials in the .env file
4. **Database Issues**:
   - SQLite (dev): delete `data/vanta.db` and restart
   - Postgres (prod): run `flask db upgrade` and verify `DATABASE_URI`
5. **CORS Errors**: Ensure `CORS_ORIGINS` includes your exact frontend URL

### Debug Mode
```bash
# Run with debug logging
python3 bin/run.py --web --debug

# Check logs
tail -f data/logs/vanta.log
```