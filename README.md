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

- **4-Tier Layered Architecture (N-Tier)**:
  1. **API Layer** (`app/api/`) - HTTP request/response handling
  2. **Service Layer** (`app/services/`) - Business logic and external integrations
  3. **Data Layer** (`app/store.py`) - Storage abstraction with repository pattern
  4. **Model Layer** (`app/schemas.py`) - Data validation and transfer objects
 
- **Privacy Protection**: 
  - PII scrubbing in logs (emails masked, IDs hashed) for GDPR compliance
- **Background Processing**: Webhook accepts requests immediately and processes enrichment asynchronously using FastAPI BackgroundTasks
- **Automatic Retry**: Transient Okta API failures are retried automatically with exponential backoff (3 attempts max)
- **Clear API versioning** (`/v1`).
- **Async/Await**: Full async implementation using `httpx` for non-blocking Okta API calls
- **Schemas** via Pydantic v2, request/response models with explicit types.
- **Separation of concerns**: schemas, services (`okta_loader`), and store.
- **Structured logging** and proper HTTP status codes (`202`, `404`).


---

## Tech Choices and Rationale

### Core Framework: FastAPI (with Pydantic v2 & pydantic-settings)

- Modern async Python framework with non-blocking I/O
- Automatic OpenAPI documentation
- Pydantic v2 and pyndantic setting integration for data validation and configuration
- High performance 
- Modern Python type hints throughout


### HTTP Client: httpx (Async)


- Full async/await support (requests is synchronous)
- Won't block FastAPI's event loop
- Modern API consistent with requests
- Better timeout handling



### Logging: Structured JSON Logging


- Machine-readable for log aggregation tools 
- Context-aware with extra fields
- Easy to query and filter
- Production-ready format



### Security: PII Scrubbing + Retry Mechanism


- GDPR compliance requirement
- Prevents accidental data leaks in logs
- Protects user privacy by default
- Handles transient network failures
- Respects Okta rate limits (backoff prevents hammering)
- Improves reliability without manual intervention


### Storage: In-Memory (Intentional Limitation)

-  Simplest possible implementation
-  Zero external dependencies
-  Fast lookups (O(1))
-  Easy to test and develop
-  Easy to swap later (dependency injection pattern used)

---

## Trade-offs and Challenges

###  **Critical Limitations**

#### 1. In-Memory Storage (Data Loss on Restart)

**Impact:**
- Complete data loss on service restart/crash
- Cannot scale horizontally (single instance only)
- No persistence across deployments


#### 2. Background Processing Complexity

-  **Pro:** Instant webhook responses (202 Accepted)
-  **Con:** Errors happen after client receives response

**Current mitigation:**
- Comprehensive error logging
- Clients must poll GET `/v1/users/{id}` to verify success
- 404 response indicates enrichment failed


#### 3. No Webhook Signature Verification

- Simplified integration (no shared secrets needed)
- Good enough for internal services
- Optional API key provides basic auth


### **High Priority Challenges**

#### 4. Optional API Key Authentication

- Easy development (no auth setup required)




#### 5. No Rate Limiting

- Simplified initial implementation
- Assumed trusted clients
- Focused on core functionality

**Risk:** Resource exhaustion, Okta API abuse, cost overruns


## Future Improvements


#### Priority 1: Data Persistence 

**Problem:** In-memory store is not production-ready

**Solutions:**

**Option A: Redis**

- Persistence across restarts
- Fast lookups (still O(1))
- Can scale horizontally

**Option B: PostgreSQL**
- Full SQL query capabilities
- Transactional integrity
- Historical data tracking
- Audit trail support

#### Priority 2: Reliability Improvements 



- Add enrichment status tracking
- Add status endpoint
- Add idempotency

#### Priority 3: Security Hardening 

- Make API key required in production
- Add webhook signature verification 
- Configure CORS properly
- Add rate limiting

#### Priority 4: Performance Optimizations 

- Parallelize Okta API calls
- Singleton HTTP client
- Add circuit breaker



#### Priority 6: Production Readiness 


- Add comprehensive testing
- Add health checks
- Failure scenario testing
- Add data retention policy
- Add proper secret management



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

