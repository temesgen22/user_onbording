# Architecture & Dependency Diagrams

## Table of Contents
1. [Module Dependency Graph](#module-dependency-graph)
2. [Class Hierarchy](#class-hierarchy)
3. [Request Flow Diagram](#request-flow-diagram)
4. [Data Model Relationships](#data-model-relationships)
5. [Service Layer Architecture](#service-layer-architecture)

---

## Module Dependency Graph

Shows how different modules import and depend on each other.

```mermaid
graph TD
    %% Main entry point
    main[app/main.py]
    
    %% API modules
    hr[app/api/hr.py]
    users[app/api/users.py]
    
    %% Core modules
    config[app/config.py]
    schemas[app/schemas.py]
    store[app/store.py]
    deps[app/dependencies.py]
    exceptions[app/exceptions.py]
    logging_config[app/logging_config.py]
    middleware[app/middleware.py]
    
    %% Services
    okta[app/services/okta_loader.py]
    
    %% External dependencies
    fastapi[FastAPI]
    pydantic[Pydantic]
    httpx[httpx]
    
    %% Main imports
    main --> hr
    main --> users
    main --> config
    main --> logging_config
    main --> middleware
    main --> exceptions
    
    %% API imports
    hr --> schemas
    hr --> okta
    hr --> deps
    hr --> store
    hr --> exceptions
    
    users --> schemas
    users --> deps
    users --> store
    users --> exceptions
    
    %% Service imports
    okta --> schemas
    okta --> config
    okta --> exceptions
    okta --> httpx
    
    %% Core imports
    deps --> store
    store --> schemas
    middleware --> config
    middleware --> exceptions
    schemas --> pydantic
    config --> pydantic
    
    %% Main uses FastAPI
    main --> fastapi
    hr --> fastapi
    users --> fastapi
    
    style main fill:#ff6b6b
    style hr fill:#4ecdc4
    style users fill:#4ecdc4
    style okta fill:#ffe66d
    style config fill:#95e1d3
    style schemas fill:#95e1d3
```

---

## Class Hierarchy

Shows all classes and their inheritance relationships.

```mermaid
classDiagram
    %% Pydantic Models
    class BaseModel {
        <<Pydantic>>
    }
    
    class HRUserIn {
        +str employee_id
        +str first_name
        +str last_name
        +Optional~str~ preferred_name
        +EmailStr email
        +Optional~str~ title
        +Optional~str~ department
        +Optional~EmailStr~ manager_email
        +Optional~str~ start_date
        ... 15 more fields
    }
    
    class OktaProfile {
        +EmailStr login
        +Optional~str~ firstName
        +Optional~str~ lastName
        +EmailStr email
        +Optional~str~ employeeNumber
    }
    
    class OktaUser {
        +OktaProfile profile
        +List~str~ groups
        +List~str~ applications
    }
    
    class EnrichedUser {
        +str id
        +str name
        +EmailStr email
        +Optional~str~ title
        +Optional~str~ department
        +Optional~str~ startDate
        +List~str~ groups
        +List~str~ applications
        +bool onboarded
        +from_sources(hr, okta) EnrichedUser$
    }
    
    %% Exception Classes
    class Exception {
        <<Python Built-in>>
    }
    
    class UserOnboardingError {
        +__init__(message)
    }
    
    class OktaAPIError {
        +Optional~int~ status_code
        +Optional~str~ email
        +__init__(message, status_code, email)
    }
    
    class OktaUserNotFoundError {
        +__init__(email)
    }
    
    class OktaConfigurationError {
        +__init__(message)
    }
    
    class UserNotFoundError {
        +str user_id
        +__init__(user_id)
    }
    
    class AuthenticationError {
        +__init__(message)
    }
    
    %% Settings Class
    class BaseSettings {
        <<Pydantic>>
    }
    
    class Settings {
        +str okta_org_url
        +str okta_api_token
        +Optional~str~ api_key
        +str log_level
        +Literal log_format
        +int api_timeout_seconds
        +validate_okta_url(v) str$
        +validate_okta_token(v) str$
        +validate_log_level(v) str$
    }
    
    %% Store Class
    class InMemoryUserStore {
        -Dict~str, EnrichedUser~ _users
        +__init__()
        +put(user_id, user) None
        +get(user_id) Optional~EnrichedUser~
    }
    
    %% Middleware
    class BaseHTTPMiddleware {
        <<Starlette>>
    }
    
    class APIKeyMiddleware {
        +List~str~ protected_paths
        +Settings settings
        +__init__(app, protected_paths)
        +dispatch(request, call_next) Response
    }
    
    %% Inheritance relationships
    BaseModel <|-- HRUserIn
    BaseModel <|-- OktaProfile
    BaseModel <|-- OktaUser
    BaseModel <|-- EnrichedUser
    BaseSettings <|-- Settings
    Exception <|-- UserOnboardingError
    UserOnboardingError <|-- OktaAPIError
    OktaAPIError <|-- OktaUserNotFoundError
    OktaAPIError <|-- OktaConfigurationError
    UserOnboardingError <|-- UserNotFoundError
    UserOnboardingError <|-- AuthenticationError
    BaseHTTPMiddleware <|-- APIKeyMiddleware
    
    %% Composition relationships
    OktaUser *-- OktaProfile : contains
    InMemoryUserStore o-- EnrichedUser : stores
```

---

## Request Flow Diagram

Shows the complete flow of a webhook request through the system.

```mermaid
sequenceDiagram
    actor Client
    participant Middleware as APIKeyMiddleware
    participant Endpoint as hr_webhook()
    participant Service as load_okta_user_by_email()
    participant Okta as Okta API
    participant Enricher as EnrichedUser.from_sources()
    participant Store as InMemoryUserStore
    
    Client->>+Middleware: POST /v1/hr/webhook<br/>{HR user data}
    
    alt API_KEY configured
        Middleware->>Middleware: Validate X-API-Key header
        alt Invalid or missing key
            Middleware-->>Client: 401/403 Unauthorized
        end
    end
    
    Middleware->>+Endpoint: Forward request
    
    Note over Endpoint: Validate HRUserIn schema
    
    Endpoint->>+Service: await load_okta_user_by_email(email)
    
    Service->>Service: get_settings()
    Service->>Service: Validate configuration
    
    Service->>+Okta: GET /api/v1/users?search=email
    Okta-->>-Service: User data
    
    alt User not found
        Service-->>Endpoint: raise OktaUserNotFoundError
        Endpoint-->>Client: 404 Not Found
    end
    
    Service->>+Okta: GET /api/v1/users/{id}/groups
    Okta-->>-Service: Groups list
    
    Service->>+Okta: GET /api/v1/users/{id}/appLinks
    Okta-->>-Service: Applications list
    
    Service->>Service: Build OktaUser model
    Service-->>-Endpoint: Return OktaUser
    
    Endpoint->>+Enricher: from_sources(hr_user, okta_user)
    Enricher->>Enricher: Merge HR + Okta data
    Enricher-->>-Endpoint: EnrichedUser
    
    Endpoint->>+Store: put(user_id, enriched_user)
    Store->>Store: Store in _users dict
    Store-->>-Endpoint: None
    
    Endpoint-->>-Middleware: 202 Accepted<br/>{enriched user}
    Middleware-->>-Client: 202 Accepted<br/>{enriched user}
```

---

## Data Model Relationships

Shows how data flows and transforms through the system.

```mermaid
graph LR
    subgraph Input
        HR[HRUserIn<br/>from webhook]
    end
    
    subgraph "External API"
        OktaAPI[Okta API]
    end
    
    subgraph "Service Layer"
        OktaUser[OktaUser<br/>profile + groups + apps]
    end
    
    subgraph "Data Transformation"
        Merger[EnrichedUser.from_sources]
    end
    
    subgraph Output
        Enriched[EnrichedUser<br/>Combined data]
    end
    
    subgraph Storage
        Store[(InMemoryUserStore)]
    end
    
    HR --> Merger
    HR -- email --> OktaAPI
    OktaAPI -- user data --> OktaUser
    OktaUser --> Merger
    Merger --> Enriched
    Enriched --> Store
    Enriched --> Client[Client Response]
    
    style HR fill:#ffe66d
    style OktaUser fill:#4ecdc4
    style Enriched fill:#95e1d3
    style Store fill:#ff6b6b
```

---

## Service Layer Architecture

Shows the async service functions and their dependencies.

```mermaid
graph TD
    subgraph "okta_loader.py"
        load[load_okta_user_by_email<br/>async]
        find[_find_okta_user_by_email<br/>async]
        groups[_get_user_groups<br/>async]
        apps[_get_user_applications<br/>async]
        headers[_auth_headers<br/>sync]
    end
    
    subgraph "External Dependencies"
        settings[get_settings]
        httpx_client[httpx.AsyncClient]
    end
    
    subgraph "Models"
        okta_model[OktaUser model]
    end
    
    subgraph "Exceptions"
        config_err[OktaConfigurationError]
        not_found[OktaUserNotFoundError]
        api_err[OktaAPIError]
    end
    
    load --> settings
    load --> find
    load --> groups
    load --> apps
    load --> okta_model
    
    find --> httpx_client
    find --> headers
    find -.raises.-> api_err
    
    groups --> httpx_client
    groups --> headers
    
    apps --> httpx_client
    apps --> headers
    
    load -.raises.-> config_err
    load -.raises.-> not_found
    load -.raises.-> api_err
    
    style load fill:#ff6b6b
    style find fill:#4ecdc4
    style groups fill:#4ecdc4
    style apps fill:#4ecdc4
```

---

## Function Call Graph

Complete function dependency tree.

```mermaid
graph TB
    subgraph "Startup"
        create_app[create_app]
        lifespan[lifespan]
        init_settings[init_settings]
        setup_logging[setup_logging]
    end
    
    subgraph "API Endpoints"
        hr_webhook[hr_webhook<br/>async]
        get_user[get_user<br/>async]
        healthz[healthz<br/>async]
    end
    
    subgraph "Dependencies"
        get_user_store[get_user_store]
        init_user_store[init_user_store]
    end
    
    subgraph "Services"
        load_okta[load_okta_user_by_email<br/>async]
        find_okta[_find_okta_user_by_email<br/>async]
        get_groups[_get_user_groups<br/>async]
        get_apps[_get_user_applications<br/>async]
        auth_headers[_auth_headers]
    end
    
    subgraph "Models"
        from_sources[EnrichedUser.from_sources<br/>classmethod]
        store_put[InMemoryUserStore.put]
        store_get[InMemoryUserStore.get]
    end
    
    subgraph "Config & Logging"
        get_settings[get_settings]
        get_logger[get_logger]
    end
    
    %% Startup flow
    create_app --> init_settings
    create_app --> setup_logging
    create_app --> lifespan
    lifespan --> init_settings
    
    %% HR webhook flow
    hr_webhook --> load_okta
    hr_webhook --> from_sources
    hr_webhook --> store_put
    hr_webhook --> get_user_store
    
    %% Get user flow
    get_user --> store_get
    get_user --> get_user_store
    
    %% Health check flow
    healthz --> get_settings
    
    %% Service flow
    load_okta --> get_settings
    load_okta --> find_okta
    load_okta --> get_groups
    load_okta --> get_apps
    
    find_okta --> auth_headers
    get_groups --> auth_headers
    get_apps --> auth_headers
    
    %% Dependencies
    get_user_store --> init_user_store
    
    style create_app fill:#ff6b6b
    style hr_webhook fill:#4ecdc4
    style get_user fill:#4ecdc4
    style load_okta fill:#ffe66d
    style from_sources fill:#95e1d3
```

---

## Middleware Pipeline

Shows the request processing pipeline.

```mermaid
graph LR
    Request[HTTP Request] --> CORS[CORSMiddleware]
    CORS --> APIKey[APIKeyMiddleware]
    APIKey --> Router[FastAPI Router]
    Router --> Endpoint[Endpoint Handler]
    Endpoint --> ExceptionHandler[Exception Handlers]
    ExceptionHandler --> Response[HTTP Response]
    
    style Request fill:#ffe66d
    style CORS fill:#95e1d3
    style APIKey fill:#ff6b6b
    style Router fill:#4ecdc4
    style Response fill:#ffe66d
```

---

## Configuration Dependency Tree

Shows how configuration flows through the application.

```mermaid
graph TD
    env[.env file]
    env_example[env.example<br/>template]
    
    env --> Settings
    
    subgraph "config.py"
        Settings[Settings class<br/>Pydantic BaseSettings]
        get_settings[get_settings]
        init_settings[init_settings]
    end
    
    Settings --> get_settings
    get_settings --> init_settings
    
    init_settings --> main[app/main.py<br/>create_app]
    get_settings --> okta[okta_loader.py<br/>load_okta_user_by_email]
    get_settings --> middleware[middleware.py<br/>APIKeyMiddleware]
    get_settings --> healthz[healthz endpoint]
    
    Settings -.validates.-> okta_url[OKTA_ORG_URL]
    Settings -.validates.-> okta_token[OKTA_API_TOKEN]
    Settings -.validates.-> api_key[API_KEY]
    Settings -.validates.-> log_level[LOG_LEVEL]
    Settings -.validates.-> log_format[LOG_FORMAT]
    
    style env fill:#ff6b6b
    style Settings fill:#4ecdc4
```

---

## Exception Handling Flow

Shows how exceptions propagate through the system.

```mermaid
graph TD
    subgraph "Okta Service"
        okta_service[load_okta_user_by_email]
    end
    
    subgraph "Raised Exceptions"
        config_err[OktaConfigurationError]
        not_found[OktaUserNotFoundError]
        api_err[OktaAPIError]
    end
    
    subgraph "API Endpoint"
        hr_endpoint[hr_webhook]
    end
    
    subgraph "Exception Handlers"
        try_catch[try/except blocks]
    end
    
    subgraph "HTTP Responses"
        resp_500[500 Internal Server Error]
        resp_404[404 Not Found]
        resp_502[502 Bad Gateway]
    end
    
    okta_service -.raises.-> config_err
    okta_service -.raises.-> not_found
    okta_service -.raises.-> api_err
    
    config_err --> try_catch
    not_found --> try_catch
    api_err --> try_catch
    
    try_catch -- OktaConfigurationError --> resp_500
    try_catch -- OktaUserNotFoundError --> resp_404
    try_catch -- OktaAPIError --> resp_502
    
    style config_err fill:#ff6b6b
    style not_found fill:#ffe66d
    style api_err fill:#ff6b6b
```

---

## Testing Structure

Shows test organization and what they test.

```mermaid
graph TD
    subgraph "Test Files"
        conftest[conftest.py<br/>Fixtures]
        test_api[test_api.py]
        test_schemas[test_schemas.py]
        test_store[test_store.py]
        test_okta[test_okta_loader.py]
    end
    
    subgraph "Fixtures"
        app_fixture[app fixture]
        client_fixture[client fixture]
        settings_fixture[test_settings fixture]
        store_fixture[user_store fixture]
        hr_fixture[sample_hr_user fixture]
        okta_fixture[sample_okta_user fixture]
    end
    
    subgraph "Tested Components"
        api[API Endpoints]
        schemas[Pydantic Models]
        store[InMemoryUserStore]
        okta_loader[Okta Service]
    end
    
    conftest --> app_fixture
    conftest --> client_fixture
    conftest --> settings_fixture
    conftest --> store_fixture
    conftest --> hr_fixture
    conftest --> okta_fixture
    
    test_api --> client_fixture
    test_api --> hr_fixture
    test_api --> okta_fixture
    test_api --> api
    
    test_schemas --> hr_fixture
    test_schemas --> okta_fixture
    test_schemas --> schemas
    
    test_store --> store_fixture
    test_store --> store
    
    test_okta --> okta_loader
    
    style conftest fill:#95e1d3
    style test_api fill:#4ecdc4
    style test_schemas fill:#4ecdc4
    style test_store fill:#4ecdc4
    style test_okta fill:#4ecdc4
```

---

## Key Observations

### 1. **Layered Architecture**
- **API Layer**: Handles HTTP requests/responses
- **Service Layer**: Business logic and external integrations
- **Data Layer**: In-memory storage
- **Clean separation** enables easy testing and maintenance

### 2. **Dependency Direction**
- Dependencies flow **downward** (API → Service → Data)
- Core modules (config, exceptions) are imported by many
- No circular dependencies

### 3. **Async Pattern**
- All API endpoints are `async`
- Okta service functions are `async`
- Uses `httpx.AsyncClient` for non-blocking I/O

### 4. **Error Handling**
- Custom exception hierarchy
- Exceptions raised in services
- Caught and transformed to HTTP responses in endpoints

### 5. **Configuration**
- Centralized in `Settings` class
- Validated at startup
- Injected via dependency injection

### 6. **Testing**
- Shared fixtures in `conftest.py`
- Mocks for external dependencies
- Tests organized by component

---

## How to Read These Diagrams

- **Boxes/Nodes**: Classes, functions, or modules
- **Arrows**: Dependencies or calls
- **Dotted arrows**: Raises exceptions or optional relationships
- **Subgraphs**: Logical grouping of related components
- **Colors**: Different component types (API, Service, Data, etc.)

---

## Viewing These Diagrams

These Mermaid diagrams can be viewed in:
- GitHub (renders automatically)
- VS Code (with Mermaid extension)
- JetBrains IDEs (with Mermaid plugin)
- Online: https://mermaid.live/

Or use any Markdown viewer that supports Mermaid syntax.

