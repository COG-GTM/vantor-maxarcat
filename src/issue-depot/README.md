# Issue Depot: Automated Bug Triage & Resolution Service

A FastAPI service that receives bug reports from various sources (Sentry, SonarQube, Datadog), assesses their severity, and creates Jira tickets for important issues using Devin as an autonomous first responder.

## Features

- **Multi-source Bug Ingestion**: Webhooks for Sentry, SonarQube, and manual bug submission
- **Automated Severity Assessment**: Heuristic-based bug classification (CRITICAL, HIGH, MEDIUM, LOW)
- **Noise Filtering**: Automatically identifies and filters non-actionable issues
- **Jira Integration**: Creates tickets in the US-Federal (UF) project via Atlassian MCP
- **Devin Dispatch**: Generates prompts for Devin to investigate and fix bugs
- **Security Compliance**: Follows STIG/NIST 800-53 guidelines for input validation and audit logging

## Quick Start

### Prerequisites

- Python 3.12+
- Poetry

### Installation

```bash
cd src/issue-depot
poetry install
```

### Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Environment variables:
- `JIRA_CLOUD_ID`: Atlassian Cloud ID (default: cog-gtm)
- `JIRA_PROJECT_KEY`: Jira project key (default: UF)
- `SENTRY_WEBHOOK_SECRET`: Secret for validating Sentry webhooks
- `DEVIN_API_KEY`: API key for Devin integration
- `DEVIN_API_URL`: Devin API endpoint

### Running the Service

```bash
poetry run fastapi dev app/main.py --port 8000
```

The service will be available at http://localhost:8000

## API Endpoints

### Health Check
```
GET /healthz
```

### Bug Reports
```
POST /api/v1/bugs              # Submit a bug report
GET  /api/v1/bugs              # List all bugs (with filtering)
GET  /api/v1/bugs/{issue_id}   # Get specific bug details
POST /api/v1/bugs/{issue_id}/create-ticket  # Create Jira ticket
```

### Webhooks
```
POST /api/v1/webhooks/sentry     # Sentry webhook receiver
POST /api/v1/webhooks/sonarqube  # SonarQube webhook receiver
```

### Devin Integration
```
POST /api/v1/dispatch-devin?issue_id={id}  # Dispatch Devin session
```

### Statistics
```
GET /api/v1/stats  # Get bug processing statistics
```

## Example Usage

### Submit a Bug Report

```bash
curl -X POST http://localhost:8000/api/v1/bugs \
  -H "Content-Type: application/json" \
  -d '{
    "source": "sentry",
    "title": "NullPointerException in UserAuthService",
    "description": "Authentication failed due to null user object",
    "error_type": "NullPointerException",
    "file_path": "auth/service.py",
    "line_number": 45,
    "repository": "COG-GTM/vantor-maxarcat",
    "environment": "production"
  }'
```

### Response

```json
{
  "issue_id": "f057125dedfbeea0",
  "assessment": {
    "is_actionable": true,
    "severity": "CRITICAL",
    "confidence": 1.0,
    "reasoning": "Contains critical keyword: authentication; Production environment increases priority",
    "suggested_action": "Create urgent Jira ticket and dispatch Devin for immediate fix",
    "affected_files": ["auth/service.py"],
    "root_cause_hypothesis": "Potential issue in auth/service.py"
  },
  "message": "Bug report received and assessed"
}
```

## Severity Assessment Logic

The service uses keyword-based heuristics to assess bug severity:

| Severity | Keywords |
|----------|----------|
| CRITICAL | security, authentication, authorization, injection, crash, data loss, corruption, outage |
| HIGH | error, exception, failed, timeout, memory leak, performance, slow, unhandled |
| NOISE | deprecation, warning, info, debug, test, development, staging |

Additional factors:
- Production environment increases priority
- Stack trace availability increases confidence
- Repository tagging enables targeted investigation

## MCP Integrations

This service is designed to work with the following MCP servers:

- **Atlassian MCP**: Create and manage Jira tickets
- **SonarQube MCP**: Query code quality issues (when available)
- **Datadog MCP**: Query logs and APM data for investigation

## Security Considerations

The service implements security controls per STIG/NIST 800-53:

- **Input Validation (V-220631/SI-10)**: All inputs are validated and sanitized
- **Audit Logging (V-220635/AU-2,AU-3)**: Security events are logged in JSON format
- **Webhook Signature Validation**: HMAC-SHA256 signature verification for Sentry webhooks

## Architecture

See the [Issue Depot Plan](../../docs/issue-depot/ISSUE_DEPOT_PLAN.md) for the full architecture documentation.

## Testing

The service was tested with:
- Manual bug submissions (various severity levels)
- Sentry webhook payloads
- SonarQube quality gate failure webhooks
- Jira ticket creation via Atlassian MCP (created UF-98)

## License

Internal use only - COG-GTM
