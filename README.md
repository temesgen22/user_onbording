## User Onboarding Integration API

A minimal FastAPI service that accepts HR user data via webhook, enriches it with Okta data fetched from Okta's API, stores it in-memory, and serves the enriched user via an API.

### Endpoints

- `POST /v1/hr/webhook` — Accept HR payload, enrich with Okta, store and return enriched user (202 Accepted)
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
# Example
$env:OKTA_ORG_URL = "https://dev-123456.okta.com"   # PowerShell
$env:OKTA_API_TOKEN = "<your-ssws-token>"
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
curl -X POST http://localhost:8000/v1/hr/webhook \\
  -H 'Content-Type: application/json' \\
  --data @data/hr_user.json
```

Then fetch the enriched user:

```bash
curl http://localhost:8000/v1/users/12345
```

### Design notes

- Clear API versioning (`/v1`).
- Schemas via Pydantic v2, request/response models with explicit types.
- Separation of concerns: schemas, services (`okta_loader`), and store.
- Structured logging and proper HTTP status codes (`202`, `404`).
- Deterministic enrichment: output aligns with example format.

### Improvements (future)

- Replace in-memory store with Redis or a database.
- Async I/O and background tasks for external calls.
- AuthN/Z (e.g., shared secret header or OAuth) and signature validation.
- Request id correlation and structured JSON logs.
- More robust validation and idempotency keys.



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

- Request body (HR webhook):

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

- Response (202 Accepted):

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

- `404 Not Found` on webhook: if Okta data is not found/matching by email address or if Okta API credentials are not configured.
- `404 Not Found` on `GET /v1/users/{id}`: if requested user is not present in the in-memory store.
- Validation errors return `422 Unprocessable Entity` from FastAPI when input does not conform to `HRUserIn`.

