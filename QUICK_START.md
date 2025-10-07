# Quick Start Guide - Updated Application

## What Changed?

Your application now has:
- ✅ **Async/await** throughout (better performance)
- ✅ **API key authentication** for security
- ✅ **Structured JSON logging** for production
- ✅ **Configuration validation** at startup
- ✅ **Proper error handling** with custom exceptions
- ✅ **Security improvements** (no secrets in logs, .gitignore)

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy the example environment file
cp env.example .env
```

Edit `.env` with your values:
```bash
# Required
OKTA_ORG_URL=https://your-org.okta.com
OKTA_API_TOKEN=your-okta-api-token

# Optional (but recommended for production)
API_KEY=your-secret-webhook-key

# Optional
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Running the Application

### Development Mode
```bash
uvicorn app.main:app --reload --port 8000
```

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Testing the API

### Health Check
```bash
curl http://localhost:8000/v1/healthz
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "okta_configured": true
}
```

### Webhook (with API Key)
If you set an `API_KEY` in your `.env`, you MUST include it:

**PowerShell:**
```powershell
$headers = @{"X-API-Key" = "your-secret-webhook-key"}
$body = Get-Content -Raw -Path data/hr_user.json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/hr/webhook `
  -Headers $headers -ContentType 'application/json' -Body $body
```

**Bash/cURL:**
```bash
curl -X POST http://localhost:8000/v1/hr/webhook \
  -H "X-API-Key: your-secret-webhook-key" \
  -H "Content-Type: application/json" \
  --data @data/hr_user.json
```

### Webhook (without API Key - Dev Mode)
If you didn't set an `API_KEY`, you can call it without the header:

```bash
curl -X POST http://localhost:8000/v1/hr/webhook \
  -H "Content-Type: application/json" \
  --data @data/hr_user.json
```

### Get User
```bash
curl http://localhost:8000/v1/users/12345
```

## Logs

Logs are now in **JSON format** by default and saved to `logs/app.log`.

Example log entry:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.api.hr",
  "message": "Successfully stored enriched user",
  "module": "hr",
  "function": "hr_webhook",
  "line": 77,
  "user_id": "12345",
  "email": "jane.doe@example.com",
  "groups_count": 3,
  "apps_count": 3
}
```

To use **text format** instead (easier for development):
```bash
# In .env
LOG_FORMAT=text
```

## Running Tests

```bash
pytest
```

Tests now properly mock the configuration, so you don't need real Okta credentials to run them.

## Common Issues

### Issue: App won't start - "OKTA_ORG_URL is required"
**Solution**: Make sure your `.env` file exists and has valid values for `OKTA_ORG_URL` and `OKTA_API_TOKEN`.

### Issue: 401 Unauthorized on webhook
**Solution**: You configured an `API_KEY`. Include the `X-API-Key` header in your request.

### Issue: 404 Not Found - "Okta user not found"
**Solution**: 
1. Check that your Okta credentials are correct
2. Verify the email in your test data exists in Okta
3. Check the logs for detailed error information

### Issue: Tests failing with import errors
**Solution**: Make sure you installed the new dependencies:
```bash
pip install -r requirements.txt
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OKTA_ORG_URL` | ✅ Yes | - | Your Okta org URL (e.g., https://dev-123.okta.com) |
| `OKTA_API_TOKEN` | ✅ Yes | - | Your Okta API token (SSWS token) |
| `API_KEY` | No | None | Secret key for webhook authentication |
| `LOG_LEVEL` | No | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_FORMAT` | No | json | json or text |
| `API_TIMEOUT_SECONDS` | No | 10 | Timeout for Okta API calls |

## Security Notes

1. **Never commit `.env` files** - they're in `.gitignore` now
2. **Use strong API keys** in production
3. **Configure CORS properly** - edit `app/main.py` line 89-95 for production
4. **Review logs** - they no longer expose sensitive data

## Next Steps

1. Review `IMPROVEMENTS.md` for full details on changes
2. Update your CI/CD pipelines with new environment variables
3. Test with your actual Okta org
4. Configure CORS for your production domains
5. Set up log aggregation (JSON format works great with ELK, Splunk, etc.)

## Need Help?

- Check `IMPROVEMENTS.md` for detailed documentation
- Review `app/config.py` for all configuration options
- Check logs at `logs/app.log` for debugging

