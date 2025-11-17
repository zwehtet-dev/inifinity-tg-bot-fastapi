#!/bin/bash

# Rollback script for FastAPI Telegram Bot
# Usage: ./scripts/rollback.sh [backup_timestamp]
# Example: ./scripts/rollback.sh 20241110_143022

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_TIMESTAMP=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"

echo -e "${YELLOW}=== FastAPI Telegram Bot Rollback ===${NC}"
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

# Check if backup timestamp is provided
if [ -z "$BACKUP_TIMESTAMP" ]; then
    print_error "Backup timestamp not provided!"
    echo ""
    echo "Usage: ./scripts/rollback.sh [backup_timestamp]"
    echo ""
    echo "Available backups:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -1 "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | sed 's/.*backup_/  /' | sed 's/.tar.gz//' || echo "  No backups found"
    else
        echo "  No backup directory found"
    fi
    exit 1
fi

# Check if backup file exists
BACKUP_FILE="$BACKUP_DIR/backup_$BACKUP_TIMESTAMP.tar.gz"
if [ ! -f "$BACKUP_FILE" ]; then
    print_error "Backup file not found: $BACKUP_FILE"
    echo ""
    echo "Available backups:"
    ls -1 "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | sed 's/.*backup_/  /' | sed 's/.tar.gz//' || echo "  No backups found"
    exit 1
fi

# Determine docker compose command
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Confirmation prompt
print_warning "This will rollback to backup: $BACKUP_TIMESTAMP"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_info "Rollback cancelled"
    exit 0
fi

# Step 1: Stop current containers
print_info "Stopping current containers..."
cd "$PROJECT_DIR"
$DOCKER_COMPOSE down || print_warning "No containers to stop"

# Step 2: Create backup of current state (before rollback)
CURRENT_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
print_info "Creating backup of current state before rollback..."
if [ -d "$PROJECT_DIR/app" ]; then
    tar -czf "$BACKUP_DIR/pre_rollback_$CURRENT_TIMESTAMP.tar.gz" -C "$PROJECT_DIR" app scripts requirements.txt
    print_info "Current state backed up: pre_rollback_$CURRENT_TIMESTAMP.tar.gz"
fi

# Step 3: Restore backup
print_info "Restoring backup from $BACKUP_TIMESTAMP..."
cd "$PROJECT_DIR"

# Remove current app and scripts directories
rm -rf app scripts

# Extract backup
tar -xzf "$BACKUP_FILE" -C "$PROJECT_DIR"
print_info "Backup restored successfully"

# Step 4: Rebuild Docker image
print_info "Rebuilding Docker image..."
$DOCKER_COMPOSE build --no-cache

# Step 5: Start containers
print_info "Starting containers..."
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
    print_error "Application failed to become healthy after rollback!"
    print_info "Check logs with: $DOCKER_COMPOSE logs bot"
    print_warning "You may need to restore manually or deploy a different version"
    exit 1
fi

# Step 7: Re-register webhook
print_info "Re-registering webhook with Telegram..."
$DOCKER_COMPOSE exec -T bot python scripts/register_webhook.py || print_warning "Webhook registration failed - may need manual setup"

# Step 8: Show container status
print_info "Container status:"
$DOCKER_COMPOSE ps

# Step 9: Show recent logs
print_info "Recent logs:"
$DOCKER_COMPOSE logs --tail=20 bot

echo ""
print_info "Rollback completed successfully!"
print_info "Rolled back to: $BACKUP_TIMESTAMP"
print_info "Current state backed up as: pre_rollback_$CURRENT_TIMESTAMP.tar.gz"
print_info "To view logs: $DOCKER_COMPOSE logs -f bot"
echo ""
