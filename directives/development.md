# Vanta Development Guide

## Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend and mobile)
- Redis (for real-time processing and caching)
- PostgreSQL (for production database)
- Expo CLI (for mobile development)
- Docker (optional, for containerized deployment)

## Technology Stack

### Backend
- **Framework**: Flask with SQLAlchemy ORM
- **Database**: PostgreSQL (production), SQLite (development)
- **Authentication**: none implemented on Flask routes (add before public deployment)
- **Real-time Processing**: Celery with Redis backend
- **Data Collection**: ScrapeCreators universal API (10+ platforms)
- **AI Analysis**: OpenRouter (default Nemotron free model; override via `OPENROUTER_MODEL`)
- **Computer Vision**: OpenCV with PIL for image analysis
- **Task Monitoring**: Flower dashboard

### Frontend
- **Web**: React 18 + TypeScript with Vite build system
- **Mobile**: React Native + Expo for cross-platform apps
- **Styling**: Tailwind CSS for responsive design
- **Charts**: Recharts for data visualization
- **State Management**: React hooks with context API

### Enterprise modules (not wired)
`app/enterprise/` contains `team_management.py`, `monetization.py`, `whitelabel.py` module code, but **no Flask route references them** — they are not exposed via the API. Treat as unintegrated.

## Project Structure

The project is organized into comprehensive components:

```
Vanta/
├── app/
│   ├── core/           # Universal API integration & analysis engine
│   ├── web/            # Flask API & database models
│   ├── desktop/        # PyQt5 GUI application
│   ├── enterprise/     # Unintegrated module code (no routes)
│   └── utils/          # Shared utilities and helpers
├── frontend/           # React + TypeScript web interface
├── mobile/             # React Native + Expo mobile apps
├── tests/              # Comprehensive test suites
├── docs/               # Complete documentation
├── scripts/            # Deployment and management scripts
└── data/               # Data storage and results
```

## Getting Started

### Backend Development
1. Clone the repository:
```bash
git clone https://github.com/fxinfo24/Vanta.git
cd Vanta
```

2. Set up Python environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-full.txt  # Full development environment
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Initialize database:
```bash
python -c "from app.web.app import create_app; from app.web.models import db; app=create_app(); app.app_context().push(); db.create_all()"
```

5. Start development server:
```bash
python3 bin/run.py --web
```

### Frontend Development
1. Install frontend dependencies:
```bash
cd frontend
npm install
```

2. Start development server:
```bash
npm run dev
```

### Mobile Development
1. Install mobile dependencies:
```bash
cd mobile
npm install
```

2. Start Expo development:
```bash
npx expo start
```

### Real-time Processing
1. Start Redis server:
```bash
# macOS: brew services start redis
# Linux: sudo systemctl start redis
# Docker: docker run -d -p 6379:6379 redis:alpine
```

2. Start Celery workers:
```bash
scripts/start_celery.sh
```

3. Monitor tasks:
```bash
# Access Flower dashboard at http://localhost:5555
```

## Testing

### Backend Tests
```bash
pytest tests/
python3 bin/run_tests.py
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Integration Tests
```bash
python -c "
from app.core.scrape_client import get_scrape_client
from app.core.openrouter_client import openrouter_client
# Test API integrations
"
```

## Deployment

### Production Database
```bash
# Set up PostgreSQL
createdb vanta
# Update DATABASE_URI in .env
```

### Docker Deployment
```bash
docker-compose up -d
```

### Cloud Deployment
- Configure auto-scaling for Celery workers
- Set up load balancer for web servers
- Use managed Redis and PostgreSQL services

## API Integration

### ScrapeCreators Setup
```python
# Configure with your API key in .env file
from app.core.scrape_client import get_scrape_client
client = get_scrape_client()
profile = client.get_twitter_profile("username")
```

### OpenRouter Setup
```python
# Configure with your API key in .env file
from app.core.openrouter_client import openrouter_client
analysis = openrouter_client.analyze_profile_content(profile_data, posts)
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Submit a pull request

## Architecture Decisions

### Universal API Approach
- Single integration point (ScrapeCreators) for 10+ platforms
- Reduced complexity vs. managing multiple APIs
- Better reliability and rate limiting

### Real-time Processing
- Celery + Redis for background task processing
- WebSocket connections for live updates
- Scalable worker architecture

### Mobile-First Design
- React Native for cross-platform compatibility
- Shared codebase between iOS and Android
- Touch-optimized user interfaces

### Enterprise Features
- Multi-tenant architecture from Day 1
- Role-based access control throughout
- White-label ready infrastructure
