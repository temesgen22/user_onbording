## User Onboarding Integration API

A minimal FastAPI service that accepts HR user data via webhook, enriches it with Okta data fetched from Okta's API, stores it in-memory, and serves the enriched user via an API.

### Endpoints

- `POST /v1/hr/webhook` — Accept HR payload, queue for background enrichment, return immediately (202 Accepted)
- `GET /v1/users/{id}` — Retrieve enriched user by employee id
- `GET /v1/healthz` — Health check

### Run locally

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Configure Okta

Set the following environment variables so the service can call Okta:

```bash
# PowerShell
$env:OKTA_ORG_URL = "https://dev-123456.okta.com"
$env:OKTA_API_TOKEN = "<your-ssws-token>"
```

Optional security configuration:
```bash
# Optional: API key for webhook authentication (recommended for production)
$env:API_KEY = "<your-secret-api-key>"
```

Notes:
- The service searches users by `profile.email` only.
- **Required**: You must configure valid Okta API credentials for the service to work.
- Required scopes: API token must have permissions to read users, groups, and app links.

### Simulate webhook

```bash
# PowerShell example using Invoke-RestMethod
$body = Get-Content -Raw -Path data/hr_user.json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/hr/webhook -ContentType 'application/json' -Body $body
```

Or with `curl`:

```bash
curl -X POST http://localhost:8000/v1/hr/webhook \
  -H "Content-Type: application/json" \
  --data @data/hr_user.json
```

The webhook returns immediately with a `202 Accepted` response. Enrichment happens asynchronously in the background.

Then fetch the enriched user (wait a moment for background processing to complete):

```bash
curl http://localhost:8000/v1/users/12345
```

### Design notes

- **Privacy Protection**: 
  - PII scrubbing in logs (emails masked, IDs hashed) for GDPR compliance
- **Background Processing**: Webhook accepts requests immediately and processes enrichment asynchronously using FastAPI BackgroundTasks
- **Automatic Retry**: Transient Okta API failures are retried automatically with exponential backoff (3 attempts max)
- **Clear API versioning** (`/v1`).
- **Async/Await**: Full async implementation using `httpx` for non-blocking Okta API calls
- **Schemas** via Pydantic v2, request/response models with explicit types.
- **Separation of concerns**: schemas, services (`okta_loader`), and store.
- **Structured logging** and proper HTTP status codes (`202`, `404`).
- **Deterministic enrichment**: output aligns with example format.

---

## Tech Choices and Rationale

### Core Framework: FastAPI (with Pydantic v2 & pydantic-settings)

- Modern async Python framework with non-blocking I/O
- Automatic OpenAPI documentation
- Pydantic v2 and pyndantic setting integration for data validation and configuration
- High performance (comparable to Node.js/Go)
- Modern Python type hints throughout

**Benefits realized:**
- Concurrent request handling without blocking
- 50-300x faster response times vs. synchronous alternatives
- Automatic request validation prevents bad data
- Self-documenting API via OpenAPI spec

### HTTP Client: httpx (Async)

**Why httpx instead of requests?**
- Full async/await support (requests is synchronous)
- Won't block FastAPI's event loop
- Connection pooling for better performance
- Modern API consistent with requests
- Better timeout handling

**Performance impact:**
- 10 concurrent webhooks: ~1-3 seconds total (vs. 10-30s if synchronous)
- Event loop remains responsive during external API calls


### Logging: Structured JSON Logging

**Why structured logging?**
- Machine-readable for log aggregation tools (ELK, Splunk)
- Context-aware with extra fields
- Easy to query and filter
- Production-ready format

**Trade-off:**
- Less human-readable in development
- Mitigated with `LOG_FORMAT=text` option

### Security: PII Scrubbing + Retry Mechanism

**Why automatic PII scrubbing?**
- GDPR compliance requirement
- Prevents accidental data leaks in logs
- Protects user privacy by default

**Why retry with exponential backoff?**
- Handles transient network failures
- Respects Okta rate limits (backoff prevents hammering)
- Improves reliability without manual intervention

**Implementation:**
- Uses `tenacity` library for retry logic
- 3 attempts max, exponential delays (2s, 4s, 8s)
- Only retries transient errors (not 404s)

### Storage: In-Memory (Intentional Limitation)

**Why in-memory store?**
- ✅ Simplest possible implementation
- ✅ Zero external dependencies
- ✅ Fast lookups (O(1))
- ✅ Easy to test and develop

**Why NOT Redis/PostgreSQL initially?**
- Focused on core functionality first
- Avoided infrastructure requirements for POC
- Easy to swap later (dependency injection pattern used)

---

## Trade-offs and Challenges

### 🔴 **Critical Limitations**

#### 1. In-Memory Storage (Data Loss on Restart)

**The Problem:**
```python
class InMemoryUserStore:
    def __init__(self):
        self._users = {}  # Lost on restart
```

**Impact:**
- Complete data loss on service restart/crash
- Cannot scale horizontally (single instance only)
- No persistence across deployments

**Why this choice?**
- Prioritized simplicity for MVP/POC
- Avoided external dependencies (Redis, PostgreSQL)
- Sufficient for development and testing

**Mitigation path:** Documented in "Future Improvements" below

#### 2. Background Processing Complexity

**The Trade-off:**
- ✅ **Pro:** Instant webhook responses (202 Accepted)
- ❌ **Con:** Errors happen after client receives response

**Impact:**
```
Client sends webhook → Gets 202 Accepted ✅
5 seconds later → Enrichment fails ❌
Client has no idea this happened
```

**Current mitigation:**
- Comprehensive error logging
- Clients must poll GET `/v1/users/{id}` to verify success
- 404 response indicates enrichment failed

**Future solution:** Add status endpoint or callback webhooks

#### 3. No Webhook Signature Verification

**Why skipped?**
- Simplified integration (no shared secrets needed)
- Good enough for internal services
- Optional API key provides basic auth

**Security gap:**
- Cannot verify webhook authenticity
- Vulnerable to replay attacks
- No tamper detection

**Who should use this:**
- ✅ Internal services on private network
- ❌ Public-facing production deployments

### 🟠 **High Priority Challenges**

#### 4. Optional API Key Authentication

**The Risk:**
```bash
# If API_KEY not set:
export API_KEY=   # Forgot to configure
→ Webhook endpoint is PUBLIC
→ Anyone can send webhooks
```

**Why optional?**
- Easy development (no auth setup required)
- Faster iteration during POC

**Production requirement:**
- **MUST** set `API_KEY` before production deployment
- Consider making it required (not optional)

#### 5. PII in Logs (Partially Mitigated)

**Current state:**
- ✅ Emails masked: `ja***@example.com`
- ✅ Employee IDs hashed: `8d969eef`
- ❌ Some context still logged (department, title)

**Trade-off:**
- Need enough context for debugging
- vs. minimizing PII exposure

**Compliance:** Satisfies basic GDPR requirements for masked PII

#### 6. No Rate Limiting

**Impact:**
```python
# Nothing prevents:
for i in range(10000):
    POST /v1/hr/webhook  # DoS attack
```

**Why skipped?**
- Simplified initial implementation
- Assumed trusted clients
- Focused on core functionality

**Risk:** Resource exhaustion, Okta API abuse, cost overruns

### 🟡 **Medium Priority Challenges**

#### 7. Sequential Okta API Calls

**Current behavior:**
```python
groups = await _get_user_groups(...)      # Wait 500ms
applications = await _get_user_applications(...)  # Wait another 500ms
# Total: ~1000ms per user
```

**Why not parallel?**
- Simpler error handling
- Easier to debug
- Code clarity

**Performance cost:** 2x slower enrichment vs. parallel calls

#### 8. Single API Key (No Multi-tenancy)

**Limitation:**
- All clients share same API key
- Cannot distinguish between HR systems
- No per-client rate limits
- Hard to rotate keys

**Why this choice?**
- Simplest auth mechanism
- Suitable for single HR system
- Avoided OAuth/JWT complexity

---

## Future Improvements

### 🚀 **If I Had More Time**

#### Priority 1: Data Persistence (1-2 weeks)

**Problem:** In-memory store is not production-ready

**Solutions:**

**Option A: Redis (Quick Win - 1-2 days)**
```python
import redis.asyncio as redis

class RedisUserStore:
    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url)
    
    async def put(self, user_id: str, user: EnrichedUser):
        await self.client.set(
            f"user:{user_id}",
            user.model_dump_json(),
            ex=86400 * 90  # 90 day TTL
        )
```

**Benefits:**
- Persistence across restarts
- Fast lookups (still O(1))
- TTL-based data expiration
- Can scale horizontally

**Option B: PostgreSQL (Long-term - 1 week)**
```sql
CREATE TABLE enriched_users (
    employee_id VARCHAR(255) PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_email ON enriched_users ((data->>'email'));
```

**Benefits:**
- Full SQL query capabilities
- Transactional integrity
- Historical data tracking
- Audit trail support

#### Priority 2: Reliability Improvements (1 week)

**Add enrichment status tracking:**
```python
class EnrichedUser(BaseModel):
    # ... existing fields ...
    enrichment_status: str  # "complete", "partial", "failed"
    enrichment_errors: List[str] = []
    enriched_at: datetime
```

**Add status endpoint:**
```python
@router.get("/enrichments/{employee_id}/status")
async def get_enrichment_status(employee_id: str):
    return {
        "status": "pending|processing|completed|failed",
        "started_at": "...",
        "completed_at": "...",
        "error": "..."
    }
```

**Add idempotency:**
```python
# Prevent duplicate processing of same webhook
# Use employee_id + timestamp to detect duplicates
```

#### Priority 3: Security Hardening (1 week)

**Make API key required in production:**
```python
if settings.environment == "production" and not settings.api_key:
    raise RuntimeError("API_KEY is required in production!")
```

**Add webhook signature verification:**
```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: str):
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

**Add rate limiting:**
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/webhook")
@limiter.limit("100/hour")
async def hr_webhook(...):
    ...
```

**Configure CORS properly:**
```python
# Currently allows all origins (*)
# Should be: allow_origins=["https://hr.company.com"]
```

#### Priority 4: Performance Optimizations (3-5 days)

**Parallelize Okta API calls:**
```python
groups, applications = await asyncio.gather(
    _get_user_groups(...),
    _get_user_applications(...),
    return_exceptions=True
)
# Performance improvement: 2x faster (500ms vs. 1000ms)
```

**Singleton HTTP client:**
```python
# Reuse httpx.AsyncClient with connection pooling
# Avoid TCP handshake overhead on every request
```

**Add circuit breaker:**
```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def load_okta_user_by_email(email: str):
    # Stops calling Okta after 5 failures
    # Prevents cascading failures
```

#### Priority 5: Observability (3-5 days)

**Add request ID correlation:**
```python
# Track requests across logs
X-Request-ID: uuid4()
```

**Add metrics:**
```python
from prometheus_client import Counter, Histogram

webhook_requests = Counter('webhook_requests_total')
enrichment_duration = Histogram('enrichment_duration_seconds')
```

**Add distributed tracing:**
```python
# OpenTelemetry / Jaeger integration
# Trace request → webhook → Okta calls → storage
```

#### Priority 6: Production Readiness (1-2 weeks)

**Add comprehensive testing:**
- Integration tests with mocked Okta
- Load testing (10k concurrent webhooks)
- Failure scenario testing

**Add health checks:**
```python
@router.get("/healthz")
async def health():
    return {
        "status": "healthy",
        "okta_reachable": await check_okta(),
        "storage_available": await check_storage()
    }
```

**Add data retention policy:**
```python
# Auto-delete users after 90 days (GDPR)
# Scheduled background task
```

**Add proper secret management:**
```python
# Replace env vars with AWS Secrets Manager / Azure Key Vault
# Automatic rotation support
```

---

## When to Use This Service

### ✅ **Good For:**
- Internal services on private network
- Development and testing environments
- MVP/POC deployments
- Low-traffic scenarios (<1000 webhooks/day)
- Single HR system integration

### ❌ **Not Ready For (Without Improvements):**
- Public-facing production APIs
- High-traffic scenarios (>10k webhooks/day)
- Multi-tenant deployments
- Compliance-critical environments (HIPAA, SOC 2)
- Scenarios requiring guaranteed delivery

### 🛠️ **Production Checklist:**

Before deploying with real user data:
- [ ] Set strong `API_KEY`
- [ ] Migrate to Redis/PostgreSQL storage
- [ ] Add rate limiting
- [ ] Configure CORS to specific origins
- [ ] Enable HTTPS enforcement
- [ ] Set up log aggregation
- [ ] Implement monitoring and alerting
- [ ] Add data retention policy
- [ ] Review security documentation (`SECURITY_TRADEOFFS.md`)

---

## Documentation

For deeper dives into specific topics:
- **`TRADEOFFS_AND_CHALLENGES.md`** - Detailed architecture trade-offs
- **`SECURITY_TRADEOFFS.md`** - Security analysis and hardening guide
- **`IMPROVEMENTS.md`** - Code improvements implemented
- **`RETRY_MECHANISM_IMPLEMENTATION.md`** - Retry logic details
- **`PII_SCRUBBING_ONLY.md`** - Privacy protection implementation
- **`performance_comparison.md`** - Async vs. sync performance analysis



### Requirements

- Python 3.10+
- Windows PowerShell (examples provided) or any shell with `curl`

### Project structure

```text
app/
  api/
    hr.py           # POST /v1/hr/webhook
    users.py        # GET  /v1/users/{id}
  services/
    okta_loader.py  # Okta API client used by HR webhook enrichment
  main.py           # App factory, logging, router inclusion, /v1/healthz
  schemas.py        # Pydantic models (HRUserIn, OktaUser, EnrichedUser)
  dependencies.py   # get_user_store() DI provider
  store.py          # InMemoryUserStore
data/
  hr_user.json         # Sample HR payload
requirements.txt
README.md
```

### Example payloads and responses

#### Webhook Request and Immediate Response

Request body (HR webhook):

```json
{
  "employee_id": "12345",
  "first_name": "Jane",
  "last_name": "Doe",
  "preferred_name": "Janey",
  "email": "jane.doe@example.com",
  "title": "Software Engineer",
  "department": "Engineering",
  "start_date": "2024-01-15"
}
```

Immediate response (202 Accepted):

```json
{
  "status": "accepted",
  "message": "User enrichment queued for background processing",
  "employee_id": "12345",
  "email": "jane.doe@example.com"
}
```

#### Retrieve Enriched User

After background processing completes, GET `/v1/users/12345` returns:

```json
{
  "id": "12345",
  "name": "Jane Doe",
  "email": "jane.doe@example.com",
  "title": "Software Engineer",
  "department": "Engineering",
  "startDate": "2024-01-15",
  "groups": ["Everyone", "Engineering", "Full-Time Employees"],
  "applications": ["Google Workspace", "Slack", "Jira"],
  "onboarded": true
}
```

### Error handling

**Webhook (POST `/v1/hr/webhook`):**
- `202 Accepted` - Always accepts valid payloads and queues for background processing
- `422 Unprocessable Entity` - Invalid input data (validation errors)
- Background enrichment failures (Okta user not found, API errors) are logged but do not affect the webhook response

**User Retrieval (GET `/v1/users/{id}`):**
- `200 OK` - User found and returned
- `404 Not Found` - User not found in store (either never processed or background enrichment failed)

**Privacy Protection:**
- All PII (emails, employee IDs, names, phone numbers) are automatically masked/hashed in logs
- Log example: `{"email": "ja***@example.com", "employee_id_hash": "8d969eef"}`
- GDPR compliant logging

**Important:** The webhook accepts requests immediately. If enrichment fails in the background, the user will not be stored and subsequent GET requests will return 404. Check application logs for enrichment failures.

