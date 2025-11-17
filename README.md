# Telegram Bot Engine - FastAPI

FastAPI-based Telegram bot with webhook support, AI-powered receipt verification, and event-driven architecture.

[![CI](https://github.com/your-username/your-repo/workflows/CI%20-%20Test%20and%20Lint/badge.svg)](https://github.com/your-username/your-repo/actions)
[![Docker Build](https://github.com/your-username/your-repo/workflows/Docker%20Build%20and%20Push/badge.svg)](https://github.com/your-username/your-repo/actions)
[![Security Scan](https://github.com/your-username/your-repo/workflows/Security%20Scan/badge.svg)](https://github.com/your-username/your-repo/actions)

## Project Structure

```
inifinity-tg-bot-fastapi/
├── app/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # FastAPI application entry point
│   ├── config.py             # Configuration management
│   ├── logging_config.py     # Logging configuration
│   ├── handlers/             # Webhook and message handlers
│   ├── services/             # Business logic services (OCR, notifications, etc.)
│   ├── models/               # Pydantic models and data structures
│   └── utils/                # Utility functions and helpers
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## Setup

### 1. Create Virtual Environment

```bash
cd inifinity-tg-bot-fastapi
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual configuration values
```

### 4. Run the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Environment Variables

See `.env.example` for all required environment variables:

- **Telegram Configuration**: Bot token, webhook URL, and secret
- **Backend Configuration**: Backend API URL and webhook secret
- **OpenAI Configuration**: API key for OCR
- **Admin Group Configuration**: Group ID and topic IDs
- **Application Configuration**: Log level, environment, host, and port

## Features

- ✅ FastAPI-based webhook architecture
- ✅ Structured JSON logging
- ✅ Environment-based configuration with validation
- ✅ Health check endpoint
- ⏳ Telegram webhook handlers (coming in next tasks)
- ⏳ AI-powered receipt verification (coming in next tasks)
- ⏳ Admin notification system (coming in next tasks)

## API Endpoints

### Health Check
```
GET /health
```

Returns application health status and version.

## Development

### Project Structure Guidelines

- **handlers/**: Contains webhook endpoints and message routing logic
- **services/**: Contains business logic (OCR, state management, notifications)
- **models/**: Contains Pydantic models for data validation
- **utils/**: Contains helper functions and utilities

### Logging

The application uses structured JSON logging in production and human-readable logs in development.

```python
from app.logging_config import get_logger, log_with_context

logger = get_logger(__name__)

# Simple logging
logger.info("Processing order")

# Logging with context
log_with_context(
    logger, 
    "info", 
    "Order created",
    order_id="123",
    user_id=456,
    amount=1000.0
)
```

## Quick Start

### Using Make (Recommended)

```bash
# Install dependencies
make install

# Run locally
make run

# Run with Docker
make docker-run

# Run tests
make test

# Check code quality
make ci
```

See `make help` for all available commands.

## Deployment

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Docker Deployment

The application includes Docker support for easy deployment and consistent environments.

#### Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- `.env` file with production configuration

#### Quick Start with Docker

1. **Build and start containers:**
   ```bash
   docker-compose up -d
   ```

2. **Check container status:**
   ```bash
   docker-compose ps
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f bot
   ```

4. **Stop containers:**
   ```bash
   docker-compose down
   ```

#### Production Deployment

Use the deployment script for production deployments:

```bash
# Deploy to production
./scripts/deploy.sh production

# Deploy to staging
./scripts/deploy.sh staging
```

The deployment script will:
1. Create a backup of the current deployment
2. Pull latest code (if using git)
3. Build Docker image
4. Stop existing containers
5. Start new containers
6. Wait for health check
7. Register webhook with Telegram
8. Verify webhook registration
9. Show container status and logs

#### Rollback

If something goes wrong, you can rollback to a previous version:

```bash
# List available backups
ls -1 backups/backup_*.tar.gz

# Rollback to specific backup
./scripts/rollback.sh 20241110_143022
```

The rollback script will:
1. Stop current containers
2. Create backup of current state
3. Restore specified backup
4. Rebuild Docker image
5. Start containers
6. Wait for health check
7. Re-register webhook

#### Docker Configuration

**Dockerfile**: Multi-stage build for optimized image size
- Builder stage: Installs dependencies
- Final stage: Minimal runtime image with health checks

**docker-compose.yml**: Local development setup
- Bot service: FastAPI application
- Backend service: Flask backend (optional)
- Network: Isolated bridge network
- Volumes: Hot-reload support for development
- Health checks: Automatic container health monitoring
- Logging: JSON file driver with rotation

#### Environment Variables in Docker

All environment variables from `.env` file are automatically loaded into the container. Make sure to set:

```bash
# Required for Docker deployment
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram
BACKEND_API_URL=http://backend:5000  # Use service name for internal communication
```

#### Health Checks

The application includes built-in health checks:

- **HTTP Health Check**: `GET /health`
- **Docker Health Check**: Runs every 30 seconds
- **Startup Grace Period**: 40 seconds

#### Monitoring Logs

```bash
# Follow logs in real-time
docker-compose logs -f bot

# View last 100 lines
docker-compose logs --tail=100 bot

# View logs from specific time
docker-compose logs --since 30m bot
```

#### Troubleshooting

**Container won't start:**
```bash
# Check container logs
docker-compose logs bot

# Check container status
docker-compose ps

# Restart container
docker-compose restart bot
```

**Webhook not registered:**
```bash
# Manually register webhook
docker-compose exec bot python scripts/register_webhook.py

# Check webhook status
docker-compose exec bot python scripts/check_webhook.py
```

**Application unhealthy:**
```bash
# Check health endpoint
curl http://localhost:8000/health

# Inspect container
docker-compose exec bot sh

# View environment variables
docker-compose exec bot env
```

### Manual Deployment (Without Docker)

For manual deployment without Docker:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export $(cat .env | xargs)
   ```

3. **Run with Uvicorn:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

4. **Use process manager (recommended):**
   ```bash
   # Using systemd, supervisor, or PM2
   pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4" --name telegram-bot
   ```

### Deployment Checklist

Before deploying to production:

- [ ] Update `.env` with production values
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Configure `TELEGRAM_WEBHOOK_URL` with public HTTPS URL
- [ ] Set strong secrets for `TELEGRAM_WEBHOOK_SECRET` and `BACKEND_WEBHOOK_SECRET`
- [ ] Verify `OPENAI_API_KEY` is valid
- [ ] Configure admin group IDs and topic IDs
- [ ] Test health check endpoint
- [ ] Verify webhook registration
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Set up backup strategy
- [ ] Document rollback procedure

## License

Proprietary
