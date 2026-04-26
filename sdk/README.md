# Ginie SDK

**Python SDK for the Ginie AI-powered DAML contract generation platform.**

Generate, audit, comply, and deploy DAML smart contracts programmatically using the Ginie platform.

---

## Installation

```bash
# From the project root
pip install -e .

# Or install dependencies directly
pip install httpx
```

---

## Quick Start

```python
from sdk import GinieClient

client = GinieClient()

# Generate and deploy a contract (full pipeline)
result = client.full_pipeline(
    "Create a bond contract between issuer and investor"
)

print(f"Contract ID: {result.contract_id}")
print(f"Security Score: {result.security_score}/100")
print(f"Compliance Score: {result.compliance_score}/100")
print(f"Deploy Gate: {'PASS' if result.deploy_gate else 'FAIL'}")
```

---

## Configuration

```python
from sdk.client import GinieClient, GinieConfig

# Default - connects to localhost:8000
client = GinieClient()

# Custom URL and timeout
client = GinieClient(
    base_url="http://your-server:8000/api/v1",
    timeout=120,
)

# Advanced configuration
config = GinieConfig(
    base_url="http://localhost:8000/api/v1",
    timeout=60,
    poll_interval=3.0,      # seconds between status polls
    poll_timeout=300.0,      # max wait for completion
    canton_environment="sandbox",
)
client = GinieClient(config=config)

# Context manager
with GinieClient() as client:
    result = client.full_pipeline("Create a token contract")
```

---

## API Reference

### Contract Generation

#### `generate_contract(prompt, canton_environment=None, canton_url=None) -> str`

Submit a contract generation request. Returns a `job_id`.

```python
job_id = client.generate_contract("Create an escrow contract")
```

#### `full_pipeline(prompt, timeout=None, on_status=None) -> JobResult`

Generate a contract and wait for the full pipeline to complete.

```python
def on_status(status):
    print(f"[{status.progress}%] {status.current_step}")

result = client.full_pipeline(
    prompt="Create a bond contract",
    timeout=300,
    on_status=on_status,
)
```

#### `iterate_contract(job_id, feedback, original_code=None) -> str`

Request modifications to an existing generated contract. Returns a new `job_id`.

```python
new_job_id = client.iterate_contract(
    job_id="abc-123",
    feedback="Add a penalty clause for late delivery",
)
```

---

### Job Tracking

#### `get_status(job_id) -> JobStatus`

Get the current status of a pipeline job.

```python
status = client.get_status(job_id)
print(status.status)        # queued | running | complete | failed
print(status.progress)      # 0-100
print(status.current_step)  # Human-readable step description
```

#### `get_result(job_id) -> JobResult`

Get the full result of a completed job.

```python
result = client.get_result(job_id)
print(result.contract_id)
print(result.security_score)
print(result.generated_code)
```

#### `wait_for_completion(job_id, poll_interval=None, timeout=None, on_status=None) -> JobResult`

Poll until a job finishes, then return the full result.

```python
result = client.wait_for_completion(job_id, timeout=300)
```

---

### Security Audit

#### `run_audit(code, contract_name="Contract", compliance_profile="generic") -> AuditReport`

Run a hybrid security + compliance audit on DAML source code.

```python
audit = client.run_audit(code=daml_code, contract_name="BondContract")
print(f"Security: {audit.security_score}/100")
print(f"Deploy Gate: {'PASS' if audit.deploy_gate else 'FAIL'}")
print(f"Findings: {audit.findings_count}")
```

#### `run_audit_by_job(job_id, compliance_profile="generic") -> AuditReport`

Run audit on a completed job's generated code.

---

### Compliance

#### `run_compliance(code, contract_name="Contract", profile="nist-800-53") -> ComplianceReport`

Run compliance analysis against a specific framework.

```python
comp = client.run_compliance(code=daml_code, profile="soc2-type2")
print(f"Compliance: {comp.compliance_score}/100")
print(f"Profile: {comp.profile}")
```

Available profiles:
- `nist-800-53` - NIST 800-53 Rev 5 (Federal/Government)
- `soc2-type2` - SOC 2 Type II (SaaS/Enterprise)
- `iso27001` - ISO 27001:2022 (International)
- `defi-security` - DeFi Security (Canton DLT attacks)
- `canton-dlt` - Canton DLT Standards (DAML best practices)
- `generic` - Generic baseline

#### `list_compliance_profiles() -> dict`

List all available compliance profiles and descriptions.

---

### Reports

#### `get_audit_report(job_id, format="all") -> dict`

Get formatted audit reports (JSON, Markdown, HTML).

```python
reports = client.get_audit_report(job_id, format="markdown")
print(reports["markdown_report"])
```

---

### Health

#### `health() -> dict`

Check backend API health.

```python
h = client.health()
print(f"DAML SDK: {h['daml_sdk']}")
```

---

## Response Types

### JobStatus

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | str | Job identifier |
| `status` | str | queued, running, complete, failed |
| `current_step` | str | Human-readable pipeline step |
| `progress` | int | 0-100 progress percentage |
| `is_complete` | bool | True if status is "complete" |
| `is_failed` | bool | True if status is "failed" |
| `is_terminal` | bool | True if complete or failed |

### JobResult

| Field | Type | Description |
|-------|------|-------------|
| `contract_id` | str | Deployed contract ID |
| `package_id` | str | DAR package ID |
| `template_id` | str | Fully qualified template ID |
| `generated_code` | str | Generated DAML source code |
| `security_score` | int | Security audit score (0-100) |
| `compliance_score` | int | Compliance score (0-100) |
| `enterprise_score` | float | Combined enterprise score |
| `deploy_gate` | bool | Whether contract passed deploy gate |
| `parties` | dict | Allocated Canton party IDs |
| `explorer_link` | str | Canton explorer URL |
| `is_deployed` | bool | True if contract_id exists |

### AuditReport

| Field | Type | Description |
|-------|------|-------------|
| `security_score` | int | Security score (0-100) |
| `compliance_score` | int | Compliance score (0-100) |
| `enterprise_score` | float | Combined score |
| `deploy_gate` | bool | Deploy gate pass/fail |
| `findings_count` | int | Number of security findings |
| `executive_summary` | dict | Summary of findings |

### ComplianceReport

| Field | Type | Description |
|-------|------|-------------|
| `compliance_score` | int | Score (0-100) |
| `profile` | str | Compliance profile used |
| `executive_summary` | dict | Summary assessment |

---

## Error Handling

```python
from sdk.client.types import GinieAPIError, GinieTimeoutError

try:
    result = client.full_pipeline("Create a contract", timeout=120)
except GinieTimeoutError as e:
    print(f"Job {e.job_id} timed out after {e.elapsed:.0f}s")
except GinieAPIError as e:
    print(f"API error {e.status_code}: {e.detail}")
```

---

## Examples

```bash
# Generate and deploy
python -m sdk.examples.generate_and_deploy

# Security audit
python -m sdk.examples.audit_contract

# Full pipeline with audit + compliance + iteration
python -m sdk.examples.full_pipeline
```

---

## Running Tests

```bash
# Unit tests (types + config, no backend needed)
python -m pytest sdk/tests/test_sdk.py -v -k "TestGinieConfig or TestTypes"

# Integration tests (requires running backend + Canton)
python -m pytest sdk/tests/test_sdk.py -v

# Or run directly
python -m sdk.tests.test_sdk
```

---

## Architecture

```
sdk/
  client/
    ginie_client.py   # Core client class
    types.py           # Response types + exceptions
    config.py          # Configuration
  examples/
    generate_and_deploy.py
    audit_contract.py
    full_pipeline.py
  tests/
    test_sdk.py
  setup.py
  README.md
```

---

## Future Extensions

- [ ] JavaScript/TypeScript SDK
- [ ] CLI tool (`ginie generate`, `ginie audit`, `ginie deploy`)
- [ ] Async client support (`GinieAsyncClient`)
- [ ] Streaming status updates via WebSocket
- [ ] Batch contract generation
- [ ] SDK authentication (API keys)
- [ ] Rate limiting and retry logic
- [ ] OpenAPI spec auto-generation
