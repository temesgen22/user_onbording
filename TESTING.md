# Testing Guide for User Onboarding Integration API

This document describes how to run and understand the test suite for the User Onboarding Integration API.

## 🧪 Test Structure

The test suite is organized using pytest and includes comprehensive coverage of all components:

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Pytest fixtures and configuration
├── test_api.py              # API endpoint tests
├── test_okta_loader.py      # Okta integration tests
├── test_schemas.py          # Pydantic schema validation tests
└── test_store.py            # In-memory store tests
```

## 🚀 Quick Start

### Run All Tests
```bash
# Using pytest directly
venv\Scripts\python.exe -m pytest tests/ -v

# Using the test runner script
venv\Scripts\python.exe run_tests.py --type all --verbose
```

### Run Specific Test Categories
```bash
# API endpoint tests only
venv\Scripts\python.exe run_tests.py --type api

# Okta integration tests only
venv\Scripts\python.exe run_tests.py --type okta

# Schema validation tests only
venv\Scripts\python.exe run_tests.py --type schemas

# Store functionality tests only
venv\Scripts\python.exe run_tests.py --type store
```

## 📋 Test Categories

### 1. **Schema Tests** (`test_schemas.py`)
Tests Pydantic model validation and data transformation:
- **HRUserIn**: HR user data validation, email validation, required fields
- **OktaProfile**: Okta profile validation, email validation
- **OktaUser**: Complete Okta user structure validation
- **EnrichedUser**: User enrichment logic, name construction

**Key Test Cases:**
- ✅ Valid data parsing and validation
- ✅ Required field enforcement
- ✅ Email format validation
- ✅ Optional field handling
- ✅ Data transformation from multiple sources

### 2. **Okta Loader Tests** (`test_okta_loader.py`)
Tests the Okta API integration service:
- **Credentials**: Environment variable handling, URL/token validation
- **User Search**: Email-based user lookup, API error handling
- **Groups/Applications**: User group and application retrieval
- **Integration**: Complete user loading workflow

**Key Test Cases:**
- ✅ Environment variable configuration
- ✅ Successful Okta API calls
- ✅ Error handling for missing credentials
- ✅ User not found scenarios
- ✅ API error handling and timeouts
- ✅ Data parsing and validation

### 3. **API Endpoint Tests** (`test_api.py`)
Tests FastAPI endpoint functionality:
- **Health Check**: Basic endpoint availability
- **HR Webhook**: User enrichment workflow
- **User Retrieval**: Stored user access
- **Integration**: Complete end-to-end flows

**Key Test Cases:**
- ✅ Health endpoint returns 200 OK
- ✅ Successful webhook processing with Okta data
- ✅ 404 handling when Okta user not found
- ✅ Input validation and error responses
- ✅ Complete webhook → store → retrieve flow
- ✅ Different email address scenarios

### 4. **Store Tests** (`test_store.py`)
Tests the in-memory user storage:
- **Basic Operations**: Store and retrieve users
- **Data Integrity**: Ensure data consistency
- **Edge Cases**: Multiple users, overwrites, isolation

**Key Test Cases:**
- ✅ Store and retrieve user data
- ✅ Handle nonexistent users
- ✅ Store multiple users
- ✅ Overwrite existing users
- ✅ Minimal and complex user data
- ✅ Store instance isolation

## 🔧 Test Configuration

### Pytest Configuration (`pytest.ini`)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
```

### Fixtures (`conftest.py`)
The test suite includes comprehensive fixtures:
- **`app`**: FastAPI application instance
- **`client`**: Test client for API calls
- **`user_store`**: Fresh in-memory store for each test
- **`sample_hr_user`**: Sample HR user data
- **`sample_okta_user`**: Sample Okta user data
- **`mock_okta_credentials`**: Mock Okta API credentials
- **`cleanup_env`**: Environment variable cleanup

## 🎯 Test Scenarios

### Okta API Integration Tests
The tests verify that the application works correctly with the Okta API only approach:

1. **Missing Credentials**: Tests fail gracefully when Okta credentials are not configured
2. **Invalid Credentials**: Tests handle authentication failures
3. **User Not Found**: Tests handle cases where email doesn't exist in Okta
4. **API Errors**: Tests handle network errors and API failures
5. **Data Parsing**: Tests ensure proper parsing of Okta API responses

### Email Matching Tests
The tests verify email-based matching between HR and Okta data:

1. **Exact Match**: HR email matches Okta profile email
2. **Different Emails**: HR and Okta have different emails (HR email takes precedence)
3. **Invalid Emails**: Proper validation of email formats

### End-to-End Workflow Tests
The tests verify the complete user onboarding flow:

1. **Webhook Processing**: HR webhook → Okta lookup → user enrichment → storage
2. **User Retrieval**: Stored users can be retrieved by ID
3. **Error Handling**: Proper error responses for various failure scenarios

## 📊 Test Results

### Current Test Coverage
- **Total Tests**: 46 tests
- **Test Categories**: 4 (Schemas, Okta Loader, API, Store)
- **Status**: ✅ All tests passing

### Test Execution Time
- **Full Suite**: ~1.5 seconds
- **Individual Categories**: ~0.3-0.5 seconds each

## 🛠️ Running Tests

### Basic Commands
```bash
# Run all tests
venv\Scripts\python.exe -m pytest tests/

# Run with verbose output
venv\Scripts\python.exe -m pytest tests/ -v

# Run specific test file
venv\Scripts\python.exe -m pytest tests/test_api.py -v

# Run specific test class
venv\Scripts\python.exe -m pytest tests/test_api.py::TestHRWebhookEndpoint -v

# Run specific test method
venv\Scripts\python.exe -m pytest tests/test_api.py::TestHRWebhookEndpoint::test_hr_webhook_success -v
```

### Advanced Commands
```bash
# Run tests with coverage
venv\Scripts\python.exe -m pytest tests/ --cov=app --cov-report=html

# Run only unit tests
venv\Scripts\python.exe -m pytest tests/ -m "not integration"

# Run tests in parallel (if pytest-xdist installed)
venv\Scripts\python.exe -m pytest tests/ -n auto

# Stop on first failure
venv\Scripts\python.exe -m pytest tests/ -x
```

### Using the Test Runner Script
```bash
# All tests with verbose output
venv\Scripts\python.exe run_tests.py --type all --verbose

# API tests with coverage
venv\Scripts\python.exe run_tests.py --type api --coverage

# Quick tests only (skip slow tests)
venv\Scripts\python.exe run_tests.py --quick
```

## 🐛 Debugging Tests

### Common Issues and Solutions

1. **Import Errors**
   ```bash
   # Ensure you're in the project root directory
   cd C:\Users\teme2\PycharmProjects\user_onboarding
   
   # Ensure virtual environment is activated
   venv\Scripts\activate
   ```

2. **Missing Dependencies**
   ```bash
   # Install all test dependencies
   venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. **Environment Issues**
   ```bash
   # Check Python path
   venv\Scripts\python.exe -c "import sys; print(sys.path)"
   
   # Verify app can be imported
   venv\Scripts\python.exe -c "from app.main import app; print('OK')"
   ```

### Test Debugging
```bash
# Run with maximum verbosity
venv\Scripts\python.exe -m pytest tests/ -vvv

# Run with print statements visible
venv\Scripts\python.exe -m pytest tests/ -s

# Run single test with debugging
venv\Scripts\python.exe -m pytest tests/test_api.py::test_hr_webhook_success -v -s
```

## 📈 Continuous Integration

The test suite is designed to be CI/CD friendly:

- **Fast Execution**: All tests run in under 2 seconds
- **Isolated Tests**: Each test is independent and can run in any order
- **Mock External Dependencies**: No real Okta API calls during testing
- **Clear Output**: Structured test results for easy parsing
- **Exit Codes**: Proper exit codes for CI/CD pipeline integration

## 🔍 Test Quality

### Best Practices Implemented
- **Arrange-Act-Assert**: Clear test structure
- **Descriptive Names**: Test names clearly describe what they test
- **Single Responsibility**: Each test focuses on one specific behavior
- **Mock External Dependencies**: No real API calls during testing
- **Comprehensive Coverage**: Tests cover happy path, edge cases, and error scenarios
- **Fast Execution**: Tests run quickly without external dependencies

### Test Maintenance
- **Fixtures**: Reusable test data and setup
- **Parameterized Tests**: Easy to add new test cases
- **Clear Documentation**: Each test class and method is well documented
- **Modular Structure**: Easy to add new test categories

The test suite provides comprehensive coverage of the User Onboarding Integration API, ensuring reliability and maintainability of the codebase.
