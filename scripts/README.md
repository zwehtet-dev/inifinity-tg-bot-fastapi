# Webhook Management Scripts

This directory contains utility scripts for managing Telegram webhook registration.

## Prerequisites

Before running these scripts, ensure you have:

1. Set up the virtual environment and installed dependencies:
   ```bash
   cd inifinity-tg-bot-fastapi
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Set the required environment variables (or create a `.env` file):
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token_here"
   export WEBHOOK_URL="https://your-domain.com/webhook/telegram"
   export TELEGRAM_WEBHOOK_SECRET="your_secret_token_here"
   ```

## Scripts

### 1. register_webhook.py

Registers the webhook with Telegram.

**Usage:**
```bash
python scripts/register_webhook.py
```

**Required Environment Variables:**
- `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather
- `WEBHOOK_URL`: The public URL where Telegram will send updates (must be HTTPS)
- `TELEGRAM_WEBHOOK_SECRET`: Secret token for webhook validation

**Example:**
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export WEBHOOK_URL="https://mybot.example.com/webhook/telegram"
export TELEGRAM_WEBHOOK_SECRET="my-secret-token-12345"
python scripts/register_webhook.py
```

**Output:**
- Validates the webhook URL format
- Registers the webhook with Telegram
- Displays webhook information including status and any errors

### 2. delete_webhook.py

Deletes the webhook from Telegram (useful for rollback or switching to polling).

**Usage:**
```bash
python scripts/delete_webhook.py
```

**Required Environment Variables:**
- `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather

**Example:**
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
python scripts/delete_webhook.py
```

**Output:**
- Shows current webhook status
- Prompts for confirmation before deletion
- Deletes the webhook if confirmed

### 3. check_webhook.py

Checks the current webhook registration status.

**Usage:**
```bash
python scripts/check_webhook.py
```

**Required Environment Variables:**
- `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather

**Example:**
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
python scripts/check_webhook.py
```

**Output:**
- Displays webhook status (active or not set)
- Shows webhook URL if registered
- Shows pending update count
- Shows any errors or warnings
- Shows last error date and message if applicable

## Webhook URL Requirements

Telegram has specific requirements for webhook URLs:

1. **Protocol**: Must use HTTPS (HTTP only allowed for localhost testing)
2. **Port**: Must use one of these ports: 443, 80, 88, or 8443
3. **No Query Parameters**: The URL cannot contain query parameters
4. **Valid Certificate**: Must have a valid SSL certificate (Let's Encrypt works fine)

## Common Issues

### Invalid Webhook URL
If you get an "Invalid webhook URL" error, check:
- URL uses HTTPS (not HTTP, unless localhost)
- Port is one of: 443, 80, 88, or 8443
- No query parameters in the URL
- Valid hostname

### Connection Errors
If Telegram cannot reach your webhook:
- Ensure your server is publicly accessible
- Check firewall rules
- Verify SSL certificate is valid
- Check that the FastAPI application is running

### Pending Updates
If you see pending updates:
- These are updates that Telegram tried to send but couldn't deliver
- They will be sent when the webhook is successfully registered
- Use `drop_pending_updates=True` in webhook registration to discard them

## Deployment Workflow

1. **Development**: Use polling or ngrok for local testing
2. **Staging**: Register webhook with staging URL
3. **Production**: Register webhook with production URL

**Example deployment:**
```bash
# Check current status
python scripts/check_webhook.py

# Register new webhook
export WEBHOOK_URL="https://production.example.com/webhook/telegram"
python scripts/register_webhook.py

# Verify registration
python scripts/check_webhook.py
```

## Rollback

If you need to rollback to polling:

```bash
# Delete the webhook
python scripts/delete_webhook.py

# Start the bot with polling instead
# (requires code changes to use polling mode)
```

## Troubleshooting

### Script fails with import errors
Make sure you're running from the project root and the virtual environment is activated:
```bash
cd inifinity-tg-bot-fastapi
source venv/bin/activate
python scripts/register_webhook.py
```

### Environment variables not found
Either export them in your shell or create a `.env` file:
```bash
# Option 1: Export in shell
export TELEGRAM_BOT_TOKEN="..."

# Option 2: Load from .env file
source .env  # or use python-dotenv
python scripts/register_webhook.py
```

### Webhook shows errors
Check the error message in the output:
```bash
python scripts/check_webhook.py
```

Common errors:
- **Connection timeout**: Server not reachable
- **SSL error**: Invalid certificate
- **Wrong response**: Application not responding correctly to webhook requests
