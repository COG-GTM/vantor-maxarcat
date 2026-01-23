# Security and Quality Audit Playbook

**Version:** 1.0  
**Created:** January 22, 2026  
**Author:** Devin AI  
**Repository:** COG-GTM/vantor-maxarcat

## Overview

This playbook documents the step-by-step process for conducting a comprehensive security and quality audit of a Python repository. It can be reused for future audits of similar repositories.

## Prerequisites

Before starting an audit, ensure you have:
- Access to the repository (clone or read permissions)
- Python virtual environment set up
- Required audit tools installed:
  - pip-audit (dependency vulnerability scanning)
  - bandit (Python security linter)
  - pylint (code quality analysis)
- Access to Jira/Atlassian for ticket creation
- Understanding of the repository's purpose and architecture

## Phase 1: Environment Setup

### 1.1 Clone and Setup Repository

```bash
cd ~/repos
git clone <repository-url>
cd <repository-name>
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 1.2 Install Audit Tools

```bash
pip install pip-audit bandit safety pylint
```

### 1.3 Create Audit Branch

```bash
git checkout -b devin/$(date +%s)-security-audit
```

## Phase 2: Automated Scanning

### 2.1 Dependency Vulnerability Scan

```bash
pip-audit
```

**What to look for:**
- Known CVEs in dependencies
- Outdated packages with security fixes available
- Development vs. runtime dependency risks

### 2.2 Security Linting with Bandit

```bash
# Scan main package
bandit -r <package_name> -f json | python -m json.tool

# Scan all Python code
bandit -r . -f json | python -m json.tool
```

**Common Bandit findings:**
- B105: Hardcoded passwords
- B101: Assert used in production
- B113: Request without timeout
- B608: SQL injection
- B301: Pickle usage

### 2.3 Code Quality Analysis with Pylint

```bash
# Errors only (critical issues)
pylint <package_name> --rcfile=/dev/null --errors-only

# Full analysis
pylint <package_name> --rcfile=/dev/null
```

**Key Pylint categories:**
- E (Error): Likely bugs
- W (Warning): Potential issues
- C (Convention): Style violations
- R (Refactor): Code smells

## Phase 3: Manual Code Review

### 3.1 Authentication and Authorization

Review for:
- Proper credential handling
- Token management and refresh
- Session security
- API key storage

**Key files to examine:**
- Authentication modules
- API client configuration
- Environment variable usage

### 3.2 Error Handling

Review for:
- Broad exception catches
- Information leakage in error messages
- Missing exception chaining
- Generic exception types

### 3.3 Input Validation

Review for:
- User input sanitization
- SQL injection vulnerabilities
- Command injection risks
- Path traversal vulnerabilities

### 3.4 Sensitive Data Handling

Review for:
- Hardcoded secrets
- Logging of sensitive data
- Credential storage
- Token exposure

## Phase 4: Documentation Review

### 4.1 Check for Outdated Information

- Python version requirements
- Dependency versions
- API compatibility warnings
- Deprecated feature usage

### 4.2 Security Documentation

- Authentication setup instructions
- Security best practices
- Known limitations

## Phase 5: Issue Documentation

### 5.1 Severity Classification

| Severity | Description | Examples |
|----------|-------------|----------|
| Critical | Immediate security risk | Auth bypass, credential exposure |
| High | Significant security concern | Token management, session issues |
| Medium | Moderate risk or quality issue | Missing timeouts, broad exceptions |
| Low | Minor issues or improvements | Code style, documentation gaps |

### 5.2 Issue Template

For each issue, document:

```markdown
## Issue ID: ISSUE-XXX

**Severity:** [Critical/High/Medium/Low]
**Location:** [file:line_numbers]
**CWE:** [CWE-XXX if applicable]
**STIG:** [V-XXXXXX if applicable]
**Tool:** [bandit/pylint/manual]

### Description
[Detailed description of the issue]

### Current Code
```python
[Code snippet showing the issue]
```

### Impact
[Potential security or quality impact]

### Recommended Fix
[Proposed solution or code change]
```

## Phase 6: Jira Ticket Creation

### 6.1 Create Epic

Create a parent Epic to track all audit findings:

```
Summary: [Security Audit] <Repository Name> Security and Quality Audit
Description: 
- Audit date
- Summary of findings by severity
- Tools used
- Link to Devin session
```

### 6.2 Create Child Tasks

For each issue, create a Task linked to the Epic:

```
Summary: [SEVERITY] ISSUE-XXX: Brief description
Description:
- Severity and location
- CWE/STIG references
- Description and impact
- Recommended fix
- Links to session and repository
```

### 6.3 Jira Configuration (cog-gtm)

```
cloudId: e395c468-f9ea-4f8f-adae-0ea6d2eb6970
projectKey: UF
Board: https://cog-gtm.atlassian.net/jira/software/projects/UF/boards/926
```

## Phase 7: Fix Implementation

### 7.1 Prioritize Fixes

1. **Quick wins**: Low effort, high impact (e.g., adding timeouts)
2. **Critical fixes**: Security vulnerabilities
3. **Quality improvements**: Code style, documentation

### 7.2 Implement and Test

```bash
# Make changes
# Run lint check
pylint <package_name> --rcfile=/dev/null --errors-only

# Run tests if available
pytest
```

## Phase 8: Pull Request Creation

### 8.1 Commit Changes

```bash
git add docs/security-audit/
git add <modified_files>
git commit -m "Add security audit report and implement fixes

- Add comprehensive security audit report
- Add triage report with prioritized issues
- Fix: Add timeout to authentication request (ISSUE-003)
- Fix: Correct missing comma in test file (ISSUE-011)
- Add audit playbook for future use"
```

### 8.2 Push and Create PR

```bash
git push origin <branch-name>
```

Use git_create_pr tool with:
- Title: "Security Audit: Comprehensive findings and fixes for <repository>"
- Base branch: master/main
- Include Devin session link in description

## Phase 9: Post-Audit Tasks

### 9.1 Update Jira Tickets

Add to each ticket:
- Link to Devin session
- Link to PR
- Repository name
- Status update

### 9.2 Wait for CI

```bash
# Use git_pr_checks to monitor CI status
# Address any CI failures
```

### 9.3 Final Report

Ensure the PR includes:
- SECURITY_AUDIT_REPORT.md - Complete findings
- TRIAGE_REPORT.md - Prioritized action items
- AUDIT_PLAYBOOK.md - This reusable playbook
- Code fixes for quick-win items

## Tools Reference

### pip-audit
- Purpose: Scan Python dependencies for known vulnerabilities
- Output: List of CVEs with fix versions
- Documentation: https://pypi.org/project/pip-audit/

### Bandit
- Purpose: Python security linter (SAST)
- Output: Security issues with CWE references
- Documentation: https://bandit.readthedocs.io/

### Pylint
- Purpose: Code quality and style analysis
- Output: Categorized issues (E/W/C/R)
- Documentation: https://pylint.pycqa.org/

### Safety (alternative to pip-audit)
- Purpose: Check dependencies against safety database
- Documentation: https://pyup.io/safety/

## Compliance Mapping

### STIG Controls

| Control | Description | Audit Focus |
|---------|-------------|-------------|
| V-220629 | Authentication | Credential handling, MFA |
| V-220630 | Session Management | Timeout, lockout |
| V-220631 | Input Validation | Sanitization, whitelisting |
| V-220632 | Injection Prevention | Parameterized queries |
| V-220633 | Encryption at Rest | AES-256 |
| V-220634 | Encryption in Transit | TLS 1.2+ |
| V-220635 | Audit Logging | Event logging |
| V-220641 | Error Handling | Generic messages, headers |

### NIST 800-53 Mapping

| NIST | STIG | Focus Area |
|------|------|------------|
| IA-2, IA-5 | V-220629 | Authentication |
| AC-7, AC-12 | V-220630 | Access Control |
| SI-10 | V-220631, V-220632 | Input Validation |
| SC-28 | V-220633 | Data Protection |
| SC-8 | V-220634 | Transmission Security |
| AU-2, AU-3 | V-220635 | Audit |
| SI-11 | V-220641 | Error Handling |

## Lessons Learned

### From vantor-maxarcat Audit

1. **Auto-generated code requires special attention**: The maxarcat_client package is auto-generated from OpenAPI specs. Issues in generated code may need to be addressed at the generator level or accepted as technical debt.

2. **Documentation often lags behind code**: The README stated Python 2.7 support while setup.py required Python 3.8+.

3. **Authentication "hacks" are common**: Developers often work around SDK limitations with direct header manipulation. These should be flagged for proper implementation.

4. **Test files can have subtle bugs**: String concatenation due to missing commas is a common Python gotcha.

5. **Timeout parameters are frequently forgotten**: The requests library doesn't have a default timeout, leading to potential hangs.

## Checklist

- [ ] Environment setup complete
- [ ] pip-audit scan completed
- [ ] Bandit scan completed
- [ ] Pylint analysis completed
- [ ] Manual code review completed
- [ ] All issues documented with severity
- [ ] Jira Epic created
- [ ] Jira tasks created for each issue
- [ ] Quick-win fixes implemented
- [ ] Lint checks pass
- [ ] PR created with all documentation
- [ ] Jira tickets updated with PR link
- [ ] CI checks pass
- [ ] Playbook updated with lessons learned
