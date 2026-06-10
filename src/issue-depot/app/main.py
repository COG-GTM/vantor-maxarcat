"""
Issue Depot: Automated Bug Triage & Resolution Service

This service receives bug reports from various sources (Sentry, SonarQube, etc.),
assesses their severity, and creates Jira tickets for important issues.
"""

import os
import json
import re
import hashlib
import hmac
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Issue Depot",
    description="Automated Bug Triage & Resolution Service powered by Devin",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JIRA_CLOUD_ID = os.getenv("JIRA_CLOUD_ID", "e395c468-f9ea-4f8f-adae-0ea6d2eb6970")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "UF")
SENTRY_WEBHOOK_SECRET = os.getenv("SENTRY_WEBHOOK_SECRET", "")
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "")
DEVIN_API_URL = os.getenv("DEVIN_API_URL", "https://api.devin.ai/v1")


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BugSource(str, Enum):
    SENTRY = "sentry"
    SONARQUBE = "sonarqube"
    DATADOG = "datadog"
    MANUAL = "manual"


class BugReport(BaseModel):
    source: BugSource
    title: str
    description: str
    severity: Optional[Severity] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    repository: Optional[str] = None
    environment: Optional[str] = None
    timestamp: Optional[str] = None
    raw_payload: Optional[dict] = None


class AssessmentResult(BaseModel):
    is_actionable: bool
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    suggested_action: str
    affected_files: list[str] = []
    root_cause_hypothesis: Optional[str] = None


class JiraTicketRequest(BaseModel):
    summary: str
    description: str
    issue_type: str = "Task"
    priority: Optional[str] = None
    labels: list[str] = []


class JiraTicketResponse(BaseModel):
    ticket_id: str
    ticket_key: str
    ticket_url: str


class DevinSessionRequest(BaseModel):
    prompt: str
    repository: Optional[str] = None
    branch: Optional[str] = None


class DevinSessionResponse(BaseModel):
    session_id: str
    session_url: str


MAX_DB_SIZE = int(os.getenv("ISSUE_DEPOT_MAX_DB_SIZE", "10000"))


class LRUDict(OrderedDict):
    """Bounded dict that evicts the least-recently-used entry once max_size is reached."""

    def __init__(self, max_size: int = MAX_DB_SIZE):
        self.max_size = max_size
        super().__init__()

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self.max_size:
            evicted_key, _ = self.popitem(last=False)
            print(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "cache_eviction",
                "details": {"evicted_key": evicted_key, "max_size": self.max_size}
            }))


issues_db: LRUDict = LRUDict()
assessments_db: LRUDict = LRUDict()


def log_security_event(event_type: str, client_ip: str, details: Optional[dict] = None):
    """Log security events per STIG V-220635 / NIST AU-2, AU-3"""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "ip": client_ip,
        "details": details or {}
    }
    print(json.dumps(log_entry))


def sanitize_string(value: str) -> str:
    """Sanitize input per STIG V-220632 / NIST SI-10"""
    if not value:
        return ""
    sanitized = re.sub(r'[<>"\';&|`$()]', '', value.strip())
    return sanitized[:2000]


def validate_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate webhook signature for security"""
    if not secret:
        return True
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def assess_bug_severity(bug: BugReport) -> AssessmentResult:
    """
    Assess bug severity based on various factors.
    This is a simplified heuristic - in production, this would use
    Devin's AI capabilities via the Datadog MCP for log analysis.
    """
    severity = Severity.LOW
    confidence = 0.5
    is_actionable = True
    reasoning_parts = []
    
    error_type = (bug.error_type or "").lower()
    title = (bug.title or "").lower()
    description = (bug.description or "").lower()
    
    critical_patterns = [
        "security", "authentication", "authorization", "injection",
        "crash", "data loss", "corruption", "outage", "down"
    ]
    high_patterns = [
        "error", "exception", "failed", "timeout", "memory leak",
        "performance", "slow", "unhandled"
    ]
    noise_patterns = [
        "deprecation", "warning", "info", "debug", "test",
        "development", "staging"
    ]
    
    combined_text = f"{error_type} {title} {description}"
    
    for pattern in critical_patterns:
        if pattern in combined_text:
            severity = Severity.CRITICAL
            confidence = 0.85
            reasoning_parts.append(f"Contains critical keyword: {pattern}")
            break
    
    if severity == Severity.LOW:
        for pattern in high_patterns:
            if pattern in combined_text:
                severity = Severity.HIGH
                confidence = 0.75
                reasoning_parts.append(f"Contains high-severity keyword: {pattern}")
                break
    
    for pattern in noise_patterns:
        if pattern in combined_text:
            if severity in [Severity.LOW, Severity.MEDIUM]:
                is_actionable = False
                confidence = 0.6
                reasoning_parts.append(f"Likely noise due to keyword: {pattern}")
    
    if bug.environment and bug.environment.lower() in ["production", "prod"]:
        if severity == Severity.LOW:
            severity = Severity.MEDIUM
        confidence = min(confidence + 0.1, 1.0)
        reasoning_parts.append("Production environment increases priority")
    
    if bug.stack_trace:
        confidence = min(confidence + 0.15, 1.0)
        reasoning_parts.append("Stack trace available for analysis")
    
    if not reasoning_parts:
        reasoning_parts.append("No specific patterns detected, using default assessment")
    
    suggested_action = "Create Jira ticket for investigation" if is_actionable else "Log and monitor"
    if severity == Severity.CRITICAL:
        suggested_action = "Create urgent Jira ticket and dispatch Devin for immediate fix"
    
    return AssessmentResult(
        is_actionable=is_actionable,
        severity=severity,
        confidence=confidence,
        reasoning="; ".join(reasoning_parts),
        suggested_action=suggested_action,
        affected_files=[bug.file_path] if bug.file_path else [],
        root_cause_hypothesis=f"Potential issue in {bug.file_path}" if bug.file_path else None
    )


def format_jira_description(bug: BugReport, assessment: AssessmentResult) -> str:
    """Format bug report as Jira ticket description"""
    description = f"""
h2. Bug Report

*Source:* {bug.source.value}
*Severity:* {assessment.severity.value}
*Environment:* {bug.environment or 'Unknown'}
*Reported:* {bug.timestamp or datetime.now(timezone.utc).isoformat()}

h3. Description
{bug.description}

h3. Assessment
*Actionable:* {'Yes' if assessment.is_actionable else 'No'}
*Confidence:* {assessment.confidence:.0%}
*Reasoning:* {assessment.reasoning}

h3. Suggested Action
{assessment.suggested_action}
"""
    
    if bug.error_type:
        description += f"\nh3. Error Type\n{bug.error_type}\n"
    
    if bug.stack_trace:
        description += f"\nh3. Stack Trace\n{{code}}\n{bug.stack_trace[:2000]}\n{{code}}\n"
    
    if bug.file_path:
        description += f"\nh3. Affected File\n{bug.file_path}"
        if bug.line_number:
            description += f" (line {bug.line_number})"
        description += "\n"
    
    if bug.repository:
        description += f"\nh3. Repository\n{bug.repository}\n"
    
    if assessment.root_cause_hypothesis:
        description += f"\nh3. Root Cause Hypothesis\n{assessment.root_cause_hypothesis}\n"
    
    description += "\n----\n_This ticket was automatically created by Issue Depot_"
    
    return description


@app.get("/healthz")
async def healthz():
    """Health check endpoint"""
    return {"status": "ok", "service": "issue-depot", "version": "1.0.0"}


@app.post("/api/v1/bugs", response_model=dict)
async def receive_bug_report(
    bug: BugReport,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Receive a bug report from any source.
    This is the main entry point for the Issue Depot workflow.
    """
    client_ip = request.client.host if request.client else "unknown"
    log_security_event("bug_report_received", client_ip, {
        "source": bug.source.value,
        "title": sanitize_string(bug.title)[:100]
    })
    
    bug.title = sanitize_string(bug.title)
    bug.description = sanitize_string(bug.description)
    
    issue_id = hashlib.sha256(
        f"{bug.source}{bug.title}{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:16]
    
    assessment = assess_bug_severity(bug)
    
    bug_data = bug.model_dump()
    bug_data.pop("raw_payload", None)
    issues_db[issue_id] = {
        "bug": bug_data,
        "assessment": assessment.model_dump(),
        "status": "assessed",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    assessments_db[issue_id] = assessment
    
    log_security_event("bug_assessed", client_ip, {
        "issue_id": issue_id,
        "severity": assessment.severity.value,
        "is_actionable": assessment.is_actionable
    })
    
    return {
        "issue_id": issue_id,
        "assessment": assessment.model_dump(),
        "message": "Bug report received and assessed"
    }


@app.get("/api/v1/bugs/{issue_id}")
async def get_bug_report(issue_id: str, request: Request):
    """Get details of a specific bug report"""
    client_ip = request.client.host if request.client else "unknown"
    
    if issue_id not in issues_db:
        log_security_event("bug_not_found", client_ip, {"issue_id": issue_id})
        raise HTTPException(status_code=404, detail="Bug report not found")
    
    log_security_event("bug_accessed", client_ip, {"issue_id": issue_id})
    return issues_db[issue_id]


@app.get("/api/v1/bugs")
async def list_bug_reports(
    request: Request,
    actionable_only: bool = False,
    severity: Optional[Severity] = None
):
    """List all bug reports with optional filtering"""
    client_ip = request.client.host if request.client else "unknown"
    log_security_event("bugs_listed", client_ip)
    
    results = []
    for issue_id, data in issues_db.items():
        assessment = data.get("assessment", {})
        
        if actionable_only and not assessment.get("is_actionable", False):
            continue
        
        if severity and assessment.get("severity") != severity.value:
            continue
        
        results.append({
            "issue_id": issue_id,
            "title": data["bug"]["title"],
            "severity": assessment.get("severity"),
            "is_actionable": assessment.get("is_actionable"),
            "status": data.get("status"),
            "created_at": data.get("created_at")
        })
    
    return {"bugs": results, "total": len(results)}


@app.post("/api/v1/bugs/{issue_id}/create-ticket", response_model=dict)
async def create_jira_ticket_for_bug(issue_id: str, request: Request):
    """
    Create a Jira ticket for a specific bug report.
    Uses the Atlassian MCP server for ticket creation.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    if issue_id not in issues_db:
        log_security_event("ticket_creation_failed", client_ip, {
            "issue_id": issue_id,
            "reason": "bug_not_found"
        })
        raise HTTPException(status_code=404, detail="Bug report not found")
    
    issue_data = issues_db[issue_id]
    bug = BugReport(**issue_data["bug"])
    assessment = AssessmentResult(**issue_data["assessment"])
    
    if not assessment.is_actionable:
        log_security_event("ticket_creation_skipped", client_ip, {
            "issue_id": issue_id,
            "reason": "not_actionable"
        })
        return {
            "message": "Bug is not actionable, skipping ticket creation",
            "issue_id": issue_id
        }
    
    summary = f"[{assessment.severity.value}] {bug.title}"
    description = format_jira_description(bug, assessment)
    
    issues_db[issue_id]["status"] = "ticket_pending"
    issues_db[issue_id]["jira_request"] = {
        "summary": summary,
        "description": description,
        "project_key": JIRA_PROJECT_KEY,
        "cloud_id": JIRA_CLOUD_ID
    }
    
    log_security_event("ticket_creation_requested", client_ip, {
        "issue_id": issue_id,
        "severity": assessment.severity.value
    })
    
    return {
        "message": "Jira ticket creation requested",
        "issue_id": issue_id,
        "ticket_request": {
            "summary": summary,
            "project_key": JIRA_PROJECT_KEY,
            "severity": assessment.severity.value
        }
    }


@app.post("/api/v1/webhooks/sentry")
async def sentry_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive webhooks from Sentry.
    Validates signature and normalizes the payload into a BugReport.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    body = await request.body()
    signature = request.headers.get("Sentry-Hook-Signature", "")
    
    if SENTRY_WEBHOOK_SECRET and not validate_webhook_signature(body, signature, SENTRY_WEBHOOK_SECRET):
        log_security_event("webhook_signature_invalid", client_ip, {"source": "sentry"})
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        log_security_event("webhook_payload_invalid", client_ip, {"source": "sentry"})
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    event_data = payload.get("data", {}).get("event", {})
    issue_data = payload.get("data", {}).get("issue", {})
    
    title = issue_data.get("title") or event_data.get("title") or "Sentry Issue"
    
    exception_data = event_data.get("exception", {})
    stack_trace = None
    error_type = None
    file_path = None
    line_number = None
    
    if exception_data and "values" in exception_data:
        exc = exception_data["values"][0] if exception_data["values"] else {}
        error_type = exc.get("type")
        
        if "stacktrace" in exc and exc["stacktrace"].get("frames"):
            frames = exc["stacktrace"]["frames"]
            stack_lines = []
            for frame in frames[-10:]:
                filename = frame.get("filename", "unknown")
                lineno = frame.get("lineno", "?")
                function = frame.get("function", "unknown")
                stack_lines.append(f"  File \"{filename}\", line {lineno}, in {function}")
            stack_trace = "\n".join(stack_lines)
            
            if frames:
                last_frame = frames[-1]
                file_path = last_frame.get("filename")
                line_number = last_frame.get("lineno")
    
    bug = BugReport(
        source=BugSource.SENTRY,
        title=sanitize_string(title),
        description=sanitize_string(event_data.get("message", "") or issue_data.get("culprit", "")),
        error_type=error_type,
        stack_trace=stack_trace,
        file_path=file_path,
        line_number=line_number,
        environment=event_data.get("environment"),
        timestamp=event_data.get("timestamp"),
        raw_payload=payload
    )
    
    log_security_event("sentry_webhook_received", client_ip, {"title": bug.title[:100]})
    
    return await receive_bug_report(bug, request, background_tasks)


@app.post("/api/v1/webhooks/sonarqube")
async def sonarqube_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive webhooks from SonarQube.
    Normalizes quality gate failures into BugReports.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        log_security_event("webhook_payload_invalid", client_ip, {"source": "sonarqube"})
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    project = payload.get("project", {})
    quality_gate = payload.get("qualityGate", {})
    
    status = quality_gate.get("status", "OK")
    if status == "OK":
        log_security_event("sonarqube_webhook_ok", client_ip, {
            "project": project.get("key")
        })
        return {"message": "Quality gate passed, no action needed"}
    
    conditions = quality_gate.get("conditions", [])
    failed_conditions = [c for c in conditions if c.get("status") == "ERROR"]
    
    description_parts = ["Quality Gate Failed:"]
    for cond in failed_conditions:
        metric = cond.get("metric", "unknown")
        value = cond.get("value", "?")
        threshold = cond.get("errorThreshold", "?")
        description_parts.append(f"- {metric}: {value} (threshold: {threshold})")
    
    bug = BugReport(
        source=BugSource.SONARQUBE,
        title=sanitize_string(f"Quality Gate Failed: {project.get('name', 'Unknown Project')}"),
        description=sanitize_string("\n".join(description_parts)),
        severity=Severity.HIGH if len(failed_conditions) > 2 else Severity.MEDIUM,
        repository=project.get("key"),
        timestamp=payload.get("analysedAt"),
        raw_payload=payload
    )
    
    log_security_event("sonarqube_webhook_received", client_ip, {
        "project": project.get("key"),
        "failed_conditions": len(failed_conditions)
    })
    
    return await receive_bug_report(bug, request, background_tasks)


@app.post("/api/v1/dispatch-devin")
async def dispatch_devin_session(
    issue_id: str,
    request: Request
):
    """
    Dispatch a Devin session to investigate or fix a bug.
    This endpoint would integrate with the Devin API.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    if issue_id not in issues_db:
        log_security_event("devin_dispatch_failed", client_ip, {
            "issue_id": issue_id,
            "reason": "bug_not_found"
        })
        raise HTTPException(status_code=404, detail="Bug report not found")
    
    issue_data = issues_db[issue_id]
    bug = BugReport(**issue_data["bug"])
    assessment = AssessmentResult(**issue_data["assessment"])
    
    prompt = f"""
You are investigating a bug report from Issue Depot.

## Bug Details
- **Title:** {bug.title}
- **Source:** {bug.source.value}
- **Severity:** {assessment.severity.value}
- **Description:** {bug.description}

## Assessment
- **Actionable:** {'Yes' if assessment.is_actionable else 'No'}
- **Confidence:** {assessment.confidence:.0%}
- **Reasoning:** {assessment.reasoning}
- **Root Cause Hypothesis:** {assessment.root_cause_hypothesis or 'None'}

## Affected Files
{chr(10).join(f'- {f}' for f in assessment.affected_files) if assessment.affected_files else 'None identified'}

## Stack Trace
{bug.stack_trace or 'Not available'}

## Your Task
1. Analyze the bug and confirm the root cause
2. If the bug is valid, implement a fix
3. Create a PR with the fix
4. Document your findings

Repository: {bug.repository or 'Not specified'}
"""
    
    issues_db[issue_id]["status"] = "devin_dispatched"
    issues_db[issue_id]["devin_prompt"] = prompt
    
    log_security_event("devin_dispatched", client_ip, {
        "issue_id": issue_id,
        "severity": assessment.severity.value
    })
    
    return {
        "message": "Devin session dispatch requested",
        "issue_id": issue_id,
        "prompt_preview": prompt[:500] + "...",
        "note": "In production, this would call the Devin API to create a session"
    }


@app.get("/api/v1/stats")
async def get_stats():
    """Get statistics about processed bugs"""
    total = len(issues_db)
    actionable = sum(1 for d in issues_db.values() if d.get("assessment", {}).get("is_actionable"))
    
    severity_counts = {}
    for data in issues_db.values():
        sev = data.get("assessment", {}).get("severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    status_counts = {}
    for data in issues_db.values():
        status = data.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "total_bugs": total,
        "actionable_bugs": actionable,
        "severity_breakdown": severity_counts,
        "status_breakdown": status_counts
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
