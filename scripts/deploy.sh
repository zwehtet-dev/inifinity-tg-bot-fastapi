#!/bin/bash

# Deployment script for FastAPI Telegram Bot
# Usage: ./scripts/deploy.sh [environment]
# Example: ./scripts/deploy.sh production

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${GREEN}=== FastAPI Telegram Bot Deployment ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Timestamp: $TIMESTAMP"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    print_error ".env file not found!"
    print_info "Please create .env file from .env.example"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed!"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed!"
    exit 1
fi

# Determine docker compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Step 1: Create backup of current deployment
print_info "Creating backup of current deployment..."
if [ -d "$PROJECT_DIR/app" ]; then
    tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" -C "$PROJECT_DIR" app scripts requirements.txt
    print_info "Backup created: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
else
    print_warning "No existing deployment found to backup"
fi

# Step 2: Pull latest code (if using git)
if [ -d "$PROJECT_DIR/.git" ]; then
    print_info "Pulling latest code from git..."
    cd "$PROJECT_DIR"
    git pull origin main || git pull origin master || print_warning "Git pull failed or not configured"
fi

# Step 3: Build Docker image
print_info "Building Docker image..."
cd "$PROJECT_DIR"
$DOCKER_COMPOSE build --no-cache

# Step 4: Stop existing containers
print_info "Stopping existing containers..."
$DOCKER_COMPOSE down || print_warning "No containers to stop"

# Step 5: Start new containers
print_info "Starting new containers..."
$DOCKER_COMPOSE up -d

# Step 6: Wait for health check
print_info "Waiting for application to be healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
HEALTH_URL="http://localhost:8000/health"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f -s "$HEALTH_URL" > /dev/null 2>&1; then
        print_info "Application is healthy!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

echo ""

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Application failed to become healthy!"
    print_info "Check logs with: $DOCKER_COMPOSE logs bot"
    print_info "To rollback, run: ./scripts/rollback.sh $TIMESTAMP"
    exit 1
fi

# Step 7: Register webhook with Telegram
print_info "Registering webhook with Telegram..."
$DOCKER_COMPOSE exec -T bot python scripts/register_webhook.py || print_warning "Webhook registration failed - may need manual setup"

# Step 8: Verify webhook registration
print_info "Verifying webhook registration..."
$DOCKER_COMPOSE exec -T bot python scripts/check_webhook.py || print_warning "Webhook verification failed"

# Step 9: Show container status
print_info "Container status:"
$DOCKER_COMPOSE ps

# Step 10: Show recent logs
print_info "Recent logs:"
$DOCKER_COMPOSE logs --tail=20 bot

# Cleanup old backups (keep last 5)
print_info "Cleaning up old backups..."
cd "$BACKUP_DIR"
ls -t backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm
print_info "Kept last 5 backups"

echo ""
print_info "Deployment completed successfully!"
print_info "To view logs: $DOCKER_COMPOSE logs -f bot"
print_info "To rollback: ./scripts/rollback.sh $TIMESTAMP"
echo ""
