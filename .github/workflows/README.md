# GitHub Actions Workflows

This directory contains all CI/CD workflows for the FastAPI Telegram Bot.

## Workflows Overview

### 1. CI - Test and Lint (`ci.yml`)

**Purpose**: Ensure code quality and functionality

**Triggers**:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

**Jobs**:
- Run tests on Python 3.11 and 3.12
- Lint with flake8
- Check formatting with black
- Check imports with isort
- Generate coverage reports
- Upload to Codecov

**Duration**: ~3-5 minutes

---

### 2. Docker Build and Push (`docker-build.yml`)

**Purpose**: Build and publish Docker images

**Triggers**:
- Push to `main`
- New tags (v*)
- Pull requests to `main`

**Jobs**:
- Build multi-platform images (amd64, arm64)
- Push to GitHub Container Registry
- Tag with version, branch, SHA
- Use BuildKit cache

**Duration**: ~5-10 minutes

---

### 3. Security Scan (`security-scan.yml`)

**Purpose**: Identify security vulnerabilities

**Triggers**:
- Push to `main` or `develop`
- Pull requests
- Weekly schedule (Sunday midnight)

**Jobs**:
- Scan dependencies with Safety
- Analyze code with Bandit
- Scan Docker images with Trivy
- Upload results to Security tab

**Duration**: ~3-5 minutes

---

### 4. PR Checks (`pr-checks.yml`)

**Purpose**: Validate pull requests

**Triggers**:
- Pull request opened/updated

**Jobs**:
- Validate PR title (semantic)
- Check for merge conflicts
- Monitor image size
- Run pylint
- Run mypy type checking

**Duration**: ~3-5 minutes

---

### 5. Deploy to Production (`deploy.yml`)

**Purpose**: Deploy to production server

**Triggers**:
- Push to `main`
- New tags (v*)
- Manual workflow dispatch

**Jobs**:
- Build production image
- Push to registry
- Deploy via SSH
- Run health checks
- Notify on failure

**Duration**: ~5-10 minutes

**Required Secrets**:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PORT`
- `DEPLOY_PATH`

---

### 6. Release (`release.yml`)

**Purpose**: Create GitHub releases

**Triggers**:
- New tags (v*)

**Jobs**:
- Generate changelog
- Create GitHub release
- Build production image
- Tag with version

**Duration**: ~5-10 minutes

---

## Workflow Dependencies

```
Push to main
    │
    ├─→ CI (tests, lint)
    │       │
    │       └─→ Docker Build
    │               │
    │               └─→ Security Scan
    │                       │
    │                       └─→ Deploy
    │
    └─→ PR Checks (if PR)
```

## Status Badges

Add these to your README.md:

```markdown
[![CI](https://github.com/USERNAME/REPO/workflows/CI%20-%20Test%20and%20Lint/badge.svg)](https://github.com/USERNAME/REPO/actions)
[![Docker](https://github.com/USERNAME/REPO/workflows/Docker%20Build%20and%20Push/badge.svg)](https://github.com/USERNAME/REPO/actions)
[![Security](https://github.com/USERNAME/REPO/workflows/Security%20Scan/badge.svg)](https://github.com/USERNAME/REPO/actions)
```

## Workflow Permissions

All workflows use:
- `contents: read` - Read repository contents
- `packages: write` - Push to GitHub Container Registry
- `security-events: write` - Upload security scan results

## Caching Strategy

- **Pip dependencies**: Cached by `setup-python` action
- **Docker layers**: Cached using GitHub Actions cache
- **BuildKit cache**: Shared across workflow runs

## Secrets Management

Secrets are stored in: Settings → Secrets and variables → Actions

Never commit secrets to the repository!

## Troubleshooting

### Workflow fails on tests
- Check Python version compatibility
- Verify all dependencies in requirements.txt
- Run tests locally first

### Docker build fails
- Check Dockerfile syntax
- Verify all files exist
- Test build locally

### Deployment fails
- Verify SSH connection
- Check server has Docker installed
- Verify .env file exists on server
- Check firewall settings

### Security scan alerts
- Review Security tab
- Update vulnerable dependencies
- Fix code issues reported by Bandit

## Best Practices

1. **Always run tests locally** before pushing
2. **Use semantic commit messages** for automatic changelogs
3. **Create PRs** for all changes (don't push directly to main)
4. **Review security scan results** regularly
5. **Keep dependencies updated** via Dependabot
6. **Monitor workflow runs** in Actions tab
7. **Test rollback procedure** periodically

## Workflow Customization

To customize workflows:

1. Edit workflow files in this directory
2. Test changes in a feature branch
3. Create PR to review changes
4. Merge to main to activate

## Manual Workflow Triggers

Some workflows can be triggered manually:

1. Go to Actions tab
2. Select workflow
3. Click "Run workflow"
4. Select branch/environment
5. Click "Run workflow"

## Monitoring

Monitor workflows:
- **Actions tab**: View all workflow runs
- **Security tab**: View security scan results
- **Packages**: View published Docker images
- **Insights → Dependency graph**: View dependencies

## Support

For workflow issues:
1. Check workflow logs in Actions tab
2. Review [CI_CD_GUIDE.md](../../CI_CD_GUIDE.md)
3. Create issue with bug report template

---

**Last Updated**: 2024-11-16
