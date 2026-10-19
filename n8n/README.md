# n8n Automation Workflows - Loan Eligibility Engine

This directory contains production-ready, exportable workflow definitions for self-hosted or cloud n8n orchestrations.

---

## Workflows Overview

| Workflow | File | Trigger | Purpose |
| :--- | :--- | :--- | :--- |
| **Workflow A** | `workflows/workflow_a_loan_discovery.json` | Daily Schedule (00:00 UTC) & Manual | Discovers public loan offers, normalizes terms, records extraction provenance, and upserts into `loan_products`. |
| **Workflow B** | `workflows/workflow_b_user_loan_matching.json` | Protected Webhook (`/webhook/user-loan-matching`) | Implements the **Optimization Funnel**: executes indexed SQL pre-filter in PostgreSQL, applies deterministic rule engine, and persists matches idempotently. |
| **Workflow C** | `workflows/workflow_c_user_notification.json` | Protected Webhook (`/webhook/user-notification`) | Queries unnotified eligible users, strictly overrides recipient to developer test inbox (`DELIVERY_MODE=test`), and records delivery audit. |

---

## Importing Workflows into n8n

1. Start n8n using Docker Compose:
   ```bash
   docker-compose up -d n8n
   ```
2. Navigate to your n8n interface (`http://localhost:5678`).
3. Click **Workflows** &rarr; **Add Workflow** &rarr; **Import from File**.
4. Select the desired workflow JSON:
   - `workflow_a_loan_discovery.json`
   - `workflow_b_user_loan_matching.json`
   - `workflow_c_user_notification.json`

---

## Credentials Configuration in n8n

### 1. PostgreSQL Credential (`postgres-loan-engine`)
Configure a PostgreSQL credential in n8n with:
- **Host**: `postgres` (within Docker network) or `localhost` (if running locally)
- **Database**: `loan_engine`
- **User**: `${POSTGRES_USER}` (e.g. `loan_app_user`)
- **Password**: `${POSTGRES_PASSWORD}`
- **Port**: `5432`
- **SSL**: `disable` (or `require` for AWS RDS)

### 2. Amazon SES Credential (Workflow C)
If using native Amazon SES node in production:
- **AWS Region**: `${AWS_REGION}` (e.g. `us-east-1`)
- **Access Key ID**: `${AWS_ACCESS_KEY_ID}`
- **Secret Access Key**: `${AWS_SECRET_ACCESS_KEY}`

---

## Critical Email Safety Guarantee

Workflow C implements a **hardware-level safety check**:
- In test mode (`DELIVERY_MODE=test`), the original email in the uploaded CSV is **never used as a destination**.
- Recipient is strictly overridden to `TEST_EMAIL_RECIPIENTS` (e.g., `developer-test-inbox@example.com` or alias `username+loan1@domain.com`).
- If no valid test recipient is specified, the workflow terminates safely without sending.
