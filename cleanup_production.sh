#!/bin/bash

# Production Cleanup Script for FastAPI Bot
# Removes all development, debug, and test files

echo "🧹 Cleaning FastAPI project for production..."
echo ""

# Remove all test files
echo "📝 Removing test files..."
rm -f test_*.py
rm -f validate_setup.py

# Remove all debug/fix documentation
echo "📝 Removing debug documentation..."
rm -f *_FIX*.md
rm -f *_DEBUG*.md
rm -f FIX_*.md
rm -f DEBUG_*.md

# Remove all implementation documentation
echo "📝 Removing implementation docs..."
rm -f *_IMPLEMENTATION*.md
rm -f TASK_*.md
rm -f *_SUMMARY.md
rm -f *_COMPLETE*.md
rm -f *_UPGRADE*.md

# Remove CI/CD development docs
echo "📝 Removing CI/CD docs..."
rm -f CI_CD_GUIDE.md
rm -f CI_WORKFLOW_GUIDE.md
rm -f QUICK_START_CICD.md
rm -f DOCKER_CICD_SUMMARY.md

# Remove specific unnecessary files
echo "📝 Removing specific files..."
rm -f ALL_FIXES_SUMMARY.md
rm -f AMOUNT_*.md
rm -f API_ENDPOINTS.md
rm -f CONFIDENCE_*.md
rm -f CONTRIBUTING.md
rm -f DEPLOY_NOW.md
rm -f DEPLOYMENT.md
rm -f FILES_CREATED.md
rm -f FINAL_SUMMARY.md
rm -f IMPLEMENTATION_COMPLETE.txt
rm -f NON_RECEIPT_*.md
rm -f OCR_UPGRADE_SUMMARY.md
rm -f QUICK_REFERENCE.md
rm -f SECURITY_WARNINGS_EXPLAINED.md
rm -f SETUP_*.md
rm -f UPGRADE_COMPLETE.md
rm -f WEIGHTED_*.md

# Remove development config files
echo "📝 Removing dev config..."
rm -f .pre-commit-config.yaml
rm -f pytest.ini
rm -f Makefile

# Remove production docker files (keep only main ones)
echo "📝 Cleaning docker files..."
rm -f docker-compose.prod.yml
rm -f Dockerfile.prod

# Remove deployment scripts (keep only docker-compose)
echo "📝 Removing deployment scripts..."
rm -f deploy-manual.sh

# Remove .github directory (CI/CD not needed in production)
echo "📝 Removing .github directory..."
rm -rf .github

# Remove docs directory (development docs)
echo "📝 Removing docs directory..."
rm -rf docs

# Remove scripts directory (development scripts)
echo "📝 Removing scripts directory..."
rm -rf scripts

# Remove pytest cache
echo "📝 Removing pytest cache..."
rm -rf .pytest_cache

# Remove __pycache__ directories
echo "📝 Removing __pycache__..."
rm -rf __pycache__
find app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove venv (should be recreated in production)
echo "📝 Removing venv..."
rm -rf venv

# Remove .env (production should have its own)
echo "📝 Removing .env (keep .env.example)..."
rm -f .env

# Remove log files
echo "📝 Removing log files..."
rm -rf app/logs/*.log 2>/dev/null

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📦 Files kept:"
echo "  - app/ (application code)"
echo "  - .env.example"
echo "  - .gitignore"
echo "  - .dockerignore"
echo "  - docker-compose.yml"
echo "  - Dockerfile"
echo "  - requirements.txt"
echo "  - README.md"
echo ""
echo "📋 Next steps:"
echo "  1. Review remaining files"
echo "  2. Create production .env file"
echo "  3. Build: docker-compose build"
echo "  4. Deploy: docker-compose up -d"
echo ""
