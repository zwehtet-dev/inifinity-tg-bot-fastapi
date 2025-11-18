#!/bin/bash
# Manual deployment script for FastAPI Telegram Bot

set -e

echo "🚀 FastAPI Telegram Bot - Manual Deployment"
echo "==========================================="
echo ""

# Configuration
IMAGE_NAME="ghcr.io/zwehtet-dev/inifinity-tg-bot-fastapi/fastapi-bot:latest"
CONTAINER_NAME="telegram-bot-fastapi"
ENV_FILE=".env"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please create .env file with your configuration:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    echo ""
    exit 1
fi

echo "✓ Found .env file"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed!"
    echo ""
    echo "Install Docker:"
    echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "  sudo sh get-docker.sh"
    echo ""
    exit 1
fi

echo "✓ Docker is installed"

# Login to GitHub Container Registry (if needed)
echo ""
echo "📦 Pulling Docker image..."
if ! docker pull "$IMAGE_NAME"; then
    echo ""
    echo "⚠️  Failed to pull image. You may need to login to GitHub Container Registry."
    echo ""
    read -p "Do you have a GitHub Personal Access Token? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "GitHub Username: " GITHUB_USER
        read -sp "GitHub Token (with read:packages scope): " GITHUB_TOKEN
        echo ""
        echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin
        echo ""
        echo "Pulling image again..."
        docker pull "$IMAGE_NAME"
    else
        echo ""
        echo "Create a token at: https://github.com/settings/tokens"
        echo "Required scope: read:packages"
        exit 1
    fi
fi

echo "✓ Image pulled successfully"

# Stop existing container
echo ""
echo "🛑 Stopping existing container (if any)..."
docker stop "$CONTAINER_NAME" 2>/dev/null || echo "  No existing container to stop"
docker rm "$CONTAINER_NAME" 2>/dev/null || echo "  No existing container to remove"

# Run new container
echo ""
echo "🚀 Starting new container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file "$ENV_FILE" \
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --health-start-period=40s \
  "$IMAGE_NAME"

echo "✓ Container started"

# Wait for health check
echo ""
echo "⏳ Waiting for health check..."
sleep 10

# Check if container is running
if docker ps | grep -q "$CONTAINER_NAME"; then
    echo "✓ Container is running"
    
    # Check health
    echo ""
    echo "🏥 Checking health endpoint..."
    if curl -f http://localhost:8000/health 2>/dev/null; then
        echo ""
        echo "✅ Deployment successful!"
        echo ""
        echo "Container: $CONTAINER_NAME"
        echo "Image: $IMAGE_NAME"
        echo "Health: http://localhost:8000/health"
        echo ""
        echo "View logs:"
        echo "  docker logs -f $CONTAINER_NAME"
        echo ""
        echo "Check status:"
        echo "  docker ps | grep $CONTAINER_NAME"
        echo ""
    else
        echo ""
        echo "⚠️  Container is running but health check failed"
        echo "Check logs:"
        echo "  docker logs $CONTAINER_NAME"
    fi
else
    echo "❌ Container failed to start"
    echo ""
    echo "Check logs:"
    echo "  docker logs $CONTAINER_NAME"
    exit 1
fi
