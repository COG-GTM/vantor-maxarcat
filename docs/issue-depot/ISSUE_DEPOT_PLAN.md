# Issue Depot: Automated Bug Triage & Resolution Plan

## Executive Summary

Issue Depot is a centralized automated bug triage system that leverages Devin as a first responder to reduce engineering overhead. When bugs are detected in Sentry or other monitoring tools, Devin autonomously investigates, assesses severity, performs root cause analysis, and either creates Jira tickets or directly fixes issues with pull requests.

This document outlines the comprehensive plan for implementing Issue Depot, including architecture, workflow, integrations, and implementation phases.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Workflow](#workflow)
3. [Architecture](#architecture)
4. [Integration Components](#integration-components)
5. [Implementation Phases](#implementation-phases)
6. [Configuration & Setup](#configuration--setup)
7. [Security Considerations](#security-considerations)
8. [Success Metrics](#success-metrics)

---

## System Overview

Issue Depot serves as the "front door" for all QA and user-reported bugs, providing automated triage and resolution capabilities through Devin. The system reduces manual engineering effort by automatically investigating bugs, determining their impact, and taking appropriate action.

### Key Capabilities

The system provides automated bug detection and ingestion from multiple sources including Sentry, Datadog, SonarQube, and manual Slack reports. It offers intelligent triage where Devin assesses whether issues are noise or genuinely impactful. Through MCP integrations, the system connects with Datadog for log analysis, Jira for ticket management, and SonarQube for code quality checks. The automated resolution capability allows Devin to create Jira tickets for tracking and optionally fix issues directly with PRs. Finally, the PR review feature enables Devin to review its own fixes for quality assurance.

---

## Workflow

The Issue Depot workflow consists of six main phases:

### Phase 1: Bug Detection & Trigger

A bug gets flagged or triggered from Sentry or another bug reporting tool. The system supports multiple input sources including Sentry webhooks for real-time error detection, Datadog alerts for APM and log-based issues, SonarQube webhooks for code quality issues, and manual Slack reports for user-reported bugs.

When a bug is detected, the source system sends a webhook payload containing the error details, stack trace, affected service/repository, severity level, and timestamp and context.

### Phase 2: Logging & Devin Session Creation

The bug gets logged and a webhook or API call spins up a Devin session. The webhook receiver service receives the incoming bug report, normalizes the data into a standard format, logs the issue for tracking and audit purposes, and dispatches a new Devin session via the Devin API.

The session is created with the appropriate repository context based on the bug's source, ensuring Devin has access to the relevant codebase.

### Phase 3: Bug Assessment & Analysis

Devin looks at the bug and assesses if it's noise or impactful. The bug is tagged to the correct codebase, and as part of the review, Devin runs the Datadog MCP scan and looks for issues.

During this phase, Devin fetches full bug details from the source (Sentry API), analyzes the stack trace and error context, queries Datadog MCP for related logs, metrics, and APM data, searches the codebase to identify affected files, checks error frequency and user impact, and makes a severity determination (noise vs. impactful).

The assessment criteria include error frequency and trend, number of affected users, business criticality of affected functionality, whether it's a regression or new issue, and availability of clear reproduction steps.

### Phase 4: Jira Ticket Creation

If deemed important, Devin uses the Jira MCP server by Atlassian and posts a task to fix. The Jira ticket includes a summary with the error type and location, a detailed description with root cause analysis, steps to reproduce (if determinable), affected files and line numbers, relevant log snippets from Datadog, proposed fix approach, and links to the original Sentry issue.

The ticket is created in the US-Federal (UF) project using the Atlassian MCP with the cloudId e395c468-f9ea-4f8f-adae-0ea6d2eb6970 and projectKey UF.

### Phase 5: Fix Implementation

Devin spins up a session to fix the task and post the PR. Devin creates a new branch following naming conventions, implements the fix based on the root cause analysis, runs existing tests to ensure no regressions, adds new tests if appropriate, creates a pull request with a detailed description linking to the Jira ticket and Sentry issue, and updates the Jira ticket with the PR link.

### Phase 6: PR Review

Devin does a PR review to ensure quality. The review checks for code correctness and completeness, adherence to coding standards, test coverage, potential side effects, and security implications. If issues are found, Devin iterates on the fix. Once approved, the PR is ready for human review and merge.

---

## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ISSUE DEPOT ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   SENTRY     │     │   DATADOG    │     │  SONARQUBE   │     │    SLACK     │
│  (Errors)    │     │  (APM/Logs)  │     │ (Code Issues)│     │  (Reports)   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │                    │
       │ Webhook            │ Alert              │ Webhook            │ Manual
       ▼                    ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                      │
│                    ┌───────────────────────┐                                 │
│                    │   Webhook Receiver    │                                 │
│                    │   (FastAPI Service)   │                                 │
│                    └───────────┬───────────┘                                 │
│                                │                                             │
│                    ┌───────────────────────┐                                 │
│                    │   Issue Normalizer    │                                 │
│                    └───────────┬───────────┘                                 │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │
                                 │ Dispatch
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DEVIN INVESTIGATION LAYER                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    DEVIN SESSION                                     │    │
│  │                                                                      │    │
│  │  1. Fetch Issue Details ──► 2. Log Analysis ──► 3. Code Search      │    │
│  │         │                        │                    │              │    │
│  │         ▼                        ▼                    ▼              │    │
│  │    [Sentry API]           [Datadog MCP]        [SonarQube MCP]      │    │
│  │                                                                      │    │
│  │  4. Severity Assessment ──► 5. Root Cause Analysis                  │    │
│  │                                    │                                 │    │
│  │                                    ▼                                 │    │
│  │                         [Decision: Noise or Impactful?]             │    │
│  │                                    │                                 │    │
│  │                    ┌───────────────┴───────────────┐                │    │
│  │                    ▼                               ▼                │    │
│  │              [NOISE]                        [IMPACTFUL]             │    │
│  │                 │                                 │                  │    │
│  │                 ▼                                 ▼                  │    │
│  │           Log & Close                    Create Jira Ticket         │    │
│  │                                          [Atlassian MCP]            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ If Impactful
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    DEVIN FIX SESSION                                 │    │
│  │                                                                      │    │
│  │  1. Create Branch ──► 2. Implement Fix ──► 3. Run Tests             │    │
│  │                                                   │                  │    │
│  │                                                   ▼                  │    │
│  │  4. Create PR ◄─────────────────────────── [Tests Pass?]            │    │
│  │       │                                                              │    │
│  │       ▼                                                              │    │
│  │  5. Self-Review PR                                                   │    │
│  │       │                                                              │    │
│  │       ▼                                                              │    │
│  │  6. Update Jira Ticket                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RESOLUTION                                              │
│                                                                              │
│         ┌─────────────────┐              ┌─────────────────┐                │
│         │   Jira Ticket   │              │   Pull Request  │                │
│         │    Created      │              │     Created     │                │
│         └─────────────────┘              └─────────────────┘                │
│                                                   │                          │
│                                                   ▼                          │
│                                          Human Review & Merge                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

The Webhook Receiver is a FastAPI service that receives incoming webhooks from Sentry, Datadog, and SonarQube. It validates webhook signatures for security, normalizes payloads into a standard format, and dispatches Devin sessions via the Devin API.

The Devin API Client manages Devin session lifecycle, creates investigation sessions with appropriate prompts and context, monitors session progress, and handles session completion and results.

The MCP Integrations include Atlassian MCP for Jira ticket creation, updates, and workflow management, Datadog MCP for log queries, APM data, and metrics analysis, and SonarQube MCP for code quality checks and issue detection.

---

## Integration Components

### Sentry Integration

Sentry serves as the primary error detection source. The integration uses webhooks for real-time notifications on issue.created and event.alert events, and the REST API for fetching detailed issue information, stack traces, and events. Authentication is via Bearer token with scopes for project:read, event:read, issue:read, and issue:write.

### Datadog MCP Integration

Datadog provides observability data for bug investigation. The available tools include log queries for searching logs around error timestamps, APM traces for request flow analysis, metrics queries for anomaly detection, and alert information for related alerts.

### Atlassian MCP Integration (Jira)

Jira serves as the ticket management system. The available tools include createJiraIssue for creating bug tickets with RCA, updateJiraIssue for updating ticket status and fields, addCommentToJiraIssue for adding investigation findings, transitionJiraIssue for moving tickets through workflow, and searchJiraIssuesUsingJql for finding related or duplicate issues.

The configuration uses cloudId e395c468-f9ea-4f8f-adae-0ea6d2eb6970 and projectKey UF for the US-Federal project.

### SonarQube MCP Integration

SonarQube provides code quality analysis. The available tools include search_sonar_issues_in_projects for finding code quality issues, get_project_quality_gate_status for checking project health, get_component_measures for getting metrics like coverage and complexity, and analyze_code_snippet for analyzing proposed fixes.

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

The goals are to set up the webhook receiver infrastructure and establish basic Devin session dispatch. The deliverables include a FastAPI webhook receiver service, Sentry webhook integration, basic Devin session creation, and logging and monitoring setup.

### Phase 2: Investigation Capabilities (Weeks 3-4)

The goals are to implement bug assessment logic and integrate MCP tools for analysis. The deliverables include Datadog MCP integration for log analysis, SonarQube MCP integration for code quality, severity assessment algorithm, and root cause analysis prompts.

### Phase 3: Ticket Management (Weeks 5-6)

The goals are to implement Jira ticket creation and establish workflow automation. The deliverables include Atlassian MCP integration, ticket template design, workflow state management, and duplicate detection.

### Phase 4: Automated Fixes (Weeks 7-8)

The goals are to enable Devin to create fixes and implement PR workflow. The deliverables include fix session orchestration, PR creation automation, self-review capability, and Jira-PR linking.

### Phase 5: Optimization & Monitoring (Weeks 9-10)

The goals are to optimize the system and add comprehensive monitoring. The deliverables include performance tuning, success metrics dashboard, feedback loop implementation, and documentation.

---

## Configuration & Setup

### Environment Variables

The required environment variables include SENTRY_AUTH_TOKEN for the Sentry API authentication token, SENTRY_ORG for the Sentry organization slug, SENTRY_CLIENT_SECRET for webhook signature verification, DEVIN_API_KEY for the Devin API authentication, JIRA_CLOUD_ID set to e395c468-f9ea-4f8f-adae-0ea6d2eb6970, and JIRA_PROJECT_KEY set to UF.

### Webhook Configuration

For Sentry, create a custom integration at Settings > Developer Settings > Custom Integrations, set the webhook URL to your receiver endpoint, enable events for issue.created and event.alert, and note the Client Secret for signature verification.

For Datadog, configure webhook notifications in Monitors, set the payload to include relevant context, and point to your webhook receiver endpoint.

### MCP Server Configuration

The Atlassian MCP is available via the organization's MCP infrastructure. The Datadog MCP is available in staging environment. The SonarQube MCP is configured for the cog-gtm organization.

---

## Security Considerations

Following STIG and NIST 800-53 guidelines, the system implements several security measures.

For authentication (IA-2, IA-5), all API tokens are stored as environment variables, webhook signatures are verified using HMAC-SHA256, and no credentials are hardcoded.

For audit logging (AU-2, AU-3), all webhook receipts are logged, all Devin session creations are logged, all Jira ticket operations are logged, and all PR creations are logged.

For input validation (SI-10), all webhook payloads are validated, issue titles and descriptions are sanitized, and Sentry issue IDs are validated.

For encryption (SC-8, SC-28), all API calls use HTTPS/TLS 1.2+, and sensitive data is encrypted at rest.

---

## Success Metrics

### Key Performance Indicators

The Mean Time to Triage (MTTT) targets less than 5 minutes from bug detection to assessment. The Noise Reduction Rate targets greater than 80% of noise issues correctly identified. The Auto-Fix Success Rate targets greater than 60% of impactful issues successfully fixed by Devin. The Ticket Quality Score targets greater than 90% of tickets containing complete RCA.

### Monitoring Dashboard

The dashboard tracks bugs received per hour/day, triage decisions (noise vs. impactful), Jira tickets created, PRs created and merged, and average resolution time.

---

## Appendix

### Sample Devin Investigation Prompt

The investigation prompt instructs Devin to investigate a bug with the issue ID, title, severity, project, and Sentry URL. It includes the error details with the culprit and stack trace. The tasks are to analyze the stack trace and error context, query Datadog for related logs and APM data, search the codebase to identify affected files, assess severity (noise vs. impactful), and if impactful, create a Jira ticket with RCA.

### Sample Jira Ticket Template

The ticket summary follows the format [Sentry #ID] Error Type in Location. The description includes sections for Root Cause Analysis with file, line, and cause; Stack Trace in a code block; Steps to Reproduce; Proposed Fix; and a link to the Sentry issue.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-22 | Devin | Initial plan document |
