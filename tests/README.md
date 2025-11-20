# Tests

This directory contains tests for the Telegram Bot FastAPI application.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_health.py
```

### Run with verbose output
```bash
pytest -v
```

## Test Structure

- `test_health.py` - Basic health checks and import tests
- `conftest.py` - Pytest configuration and shared fixtures

## Adding New Tests

1. Create a new file starting with `test_`
2. Write test functions starting with `test_`
3. Use fixtures from `conftest.py` for common setup
4. Mark async tests with `@pytest.mark.asyncio`

## CI/CD

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

## Coverage

Coverage reports are generated in:
- Terminal output
- `htmlcov/` directory (HTML report)
- `coverage.xml` (for CI tools)

Target coverage: 80%+ (aspirational)
