# Migration Checklist

Use this checklist to migrate from the old codebase to the improved version.

## ✅ Before Running the Application

### 1. Install New Dependencies
```bash
pip install -r requirements.txt
```
This adds `pydantic-settings` which is now required.

### 2. Create .env File
```bash
cp env.example .env
```

Edit `.env` and add your values:
```env
OKTA_ORG_URL=https://your-org.okta.com
OKTA_API_TOKEN=your-actual-token
```

### 3. (Optional) Add API Key for Security
Add to `.env`:
```env
API_KEY=generate-a-strong-random-key-here
```

**Note**: If you add an API_KEY, all webhook calls must include the `X-API-Key` header!

### 4. Review Log Configuration
Choose your log format in `.env`:
```env
# For production (machine-readable, works with log aggregation tools)
LOG_FORMAT=json

# For development (human-readable)
LOG_FORMAT=text

# Set log level
LOG_LEVEL=INFO
```

## ✅ Code Changes Required

### If You Have Custom Code Calling the Webhook

**Old way (still works without API_KEY):**
```python
import requests
response = requests.post(
    "http://localhost:8000/v1/hr/webhook",
    json=hr_data
)
```

**New way (with API_KEY):**
```python
import requests
response = requests.post(
    "http://localhost:8000/v1/hr/webhook",
    json=hr_data,
    headers={"X-API-Key": "your-api-key"}
)
```

### If You're Importing from the App

**Old imports (still work):**
```python
from app.services.okta_loader import load_okta_user_by_email
```

**Updated usage (now async):**
```python
# Old (synchronous)
okta_user = load_okta_user_by_email(email)

# New (asynchronous)
okta_user = await load_okta_user_by_email(email)
```

## ✅ Testing Changes

### Run Tests
```bash
pytest
```

If tests fail, check:
1. Did you install `pydantic-settings`?
2. Are there any import errors?

### Manual Testing

1. **Start the app:**
   ```bash
   uvicorn app.main:app --reload
   ```

2. **Check health endpoint:**
   ```bash
   curl http://localhost:8000/v1/healthz
   ```
   
   Should return:
   ```json
   {
     "status": "ok",
     "version": "1.0.0",
     "okta_configured": true
   }
   ```

3. **Test webhook (adjust based on your API_KEY setting):**
   ```bash
   # Without API_KEY
   curl -X POST http://localhost:8000/v1/hr/webhook \
     -H "Content-Type: application/json" \
     --data @data/hr_user.json
   
   # With API_KEY
   curl -X POST http://localhost:8000/v1/hr/webhook \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     --data @data/hr_user.json
   ```

## ✅ Deployment Changes

### Environment Variables

Update your deployment configuration to include:

**Required:**
- `OKTA_ORG_URL` (no change)
- `OKTA_API_TOKEN` (no change)

**New/Optional:**
- `API_KEY` - Recommended for production!
- `LOG_LEVEL` - Default: INFO
- `LOG_FORMAT` - Default: json
- `API_TIMEOUT_SECONDS` - Default: 10

### Example: Docker
```dockerfile
ENV OKTA_ORG_URL=https://your-org.okta.com
ENV OKTA_API_TOKEN=your-token
ENV API_KEY=your-production-api-key
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=json
```

### Example: Kubernetes ConfigMap/Secret
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  OKTA_ORG_URL: "https://your-org.okta.com"
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
---
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  OKTA_API_TOKEN: "your-token"
  API_KEY: "your-api-key"
```

### Example: Heroku
```bash
heroku config:set OKTA_ORG_URL=https://your-org.okta.com
heroku config:set OKTA_API_TOKEN=your-token
heroku config:set API_KEY=your-api-key
heroku config:set LOG_FORMAT=json
```

## ✅ Monitoring & Logging

### Log Format Changed

**Old logs (text):**
```
2024-01-15 10:30:45 INFO app.api.hr - Received HR webhook for employee_id=12345 email=jane@example.com
```

**New logs (JSON):**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.api.hr",
  "message": "Received HR webhook for employee",
  "employee_id": "12345",
  "email": "jane@example.com"
}
```

### Update Log Parsing

If you have log monitoring/alerting:
1. Update log parsers to handle JSON format
2. Update alert rules to use new field names
3. Take advantage of structured fields for better filtering

### Log Aggregation

The new JSON format works great with:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Splunk
- Datadog
- CloudWatch Logs Insights
- Papertrail

Example Elasticsearch query:
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"level": "ERROR"}},
        {"match": {"logger": "app.services.okta_loader"}}
      ]
    }
  }
}
```

## ✅ Security Checklist

- [ ] `.env` file is not committed (it's in `.gitignore`)
- [ ] Strong `API_KEY` set for production
- [ ] CORS configured properly in `app/main.py` (line 89-95)
- [ ] Okta API token has minimum required permissions
- [ ] Logs reviewed - no sensitive data exposed
- [ ] HTTPS/TLS configured (not handled by this app - do at load balancer)

## ✅ Performance Checklist

- [ ] Async operations working (check logs for async warnings)
- [ ] Connection pooling enabled (httpx handles this)
- [ ] Appropriate timeout set (`API_TIMEOUT_SECONDS`)
- [ ] Log level set to INFO or WARNING in production (not DEBUG)

## ✅ Rollback Plan

If you need to rollback:

1. **Keep the old code in git:**
   ```bash
   git tag pre-improvements
   ```

2. **If issues occur:**
   ```bash
   git revert <commit-hash>
   # or
   git checkout pre-improvements
   ```

3. **Quick fixes without rollback:**
   - Turn off API key: Remove `API_KEY` from `.env`
   - Change log format: Set `LOG_FORMAT=text` in `.env`
   - Reduce logging: Set `LOG_LEVEL=WARNING` in `.env`

## ✅ Known Breaking Changes

### 1. API Key Authentication
- **Impact**: If `API_KEY` is set, webhook calls without the header will get 401
- **Fix**: Add `X-API-Key` header or remove `API_KEY` from config

### 2. Configuration Validation
- **Impact**: App won't start if `OKTA_ORG_URL` or `OKTA_API_TOKEN` are invalid
- **Fix**: Ensure `.env` file exists with valid values

### 3. Async Functions
- **Impact**: If you import `load_okta_user_by_email`, you must `await` it
- **Fix**: Add `await` or make your function async

### 4. Log Format
- **Impact**: Log parsers expecting text format will break
- **Fix**: Update parsers or set `LOG_FORMAT=text`

## ✅ Post-Deployment Verification

After deploying:

1. **Health check returns 200:**
   ```bash
   curl https://your-domain.com/v1/healthz
   ```

2. **Webhook works:**
   ```bash
   curl -X POST https://your-domain.com/v1/hr/webhook \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     --data @test-payload.json
   ```

3. **Logs are being collected:**
   - Check your log aggregation system
   - Verify JSON parsing is working
   - Confirm no errors in startup logs

4. **Error handling works:**
   - Try with invalid data (should get 422)
   - Try with missing API key (should get 401)
   - Try with non-existent user (should get 404)

## Questions?

See:
- `QUICK_START.md` - How to run the app
- `IMPROVEMENTS.md` - Detailed list of changes
- `README.md` - Original documentation
- `env.example` - All configuration options

