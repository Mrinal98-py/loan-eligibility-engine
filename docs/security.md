# Security Architecture & Threat Model

## 1. Overview & Data Sensitivity Classification

The Loan Eligibility Engine processes financial and Personally Identifiable Information (PII) including:
- **Financial Profile**: Monthly income, credit bureau score, employment status.
- **Identity & Contact**: Legal names, personal email addresses, applicant age.
- **Derived Matches**: Banking product eligibility determinations.

Because financial records represent highly sensitive confidential data, security controls are applied across every layer of the architecture.

---

## 2. Threat Modeling & Security Controls Matrix

| Threat Category | Potential Attack Vector | Applied Mitigation in Loan Engine |
| :--- | :--- | :--- |
| **Data Ingestion** | Denial of Service via gigabyte file payloads | Enforces `MAX_FILE_SIZE_BYTES=104,857,600` (100 MB) limit at API Gateway and pre-flight validation. |
| **Malicious Payload** | Executable file masquerading as CSV | Strict MIME type validation (`text/csv`, `application/csv`) and file extension verification. |
| **Client-Side Injection** | Spreadsheet Formula Injection (`=CMD|...`, `+`, `-`, `@`) | `IngestionService._sanitize_formula()` prepends apostrophe (`'`) to all untrusted cell text. |
| **Transport Security** | Eavesdropping on CSV in transit | Direct client-to-S3 upload using TLS 1.3 and 15-minute expiring Presigned URLs. File never traverses intermediate proxies in plain text. |
| **Storage at Rest** | Unauthorized access to raw CSV bucket | Private S3 bucket with `BlockPublicAcls`, `BlockPublicPolicy`, and AWS SSE-AES256 encryption. S3 lifecycle rule expires objects after 30 days. |
| **Database Security** | SQL Injection via user data fields | Parameterized SQL queries across all SQLAlchemy and n8n PostgreSQL operations (`$1`, `$2`, `:import_id`). |
| **API Unauthorized Access**| Triggering expensive matching workflows | Protected webhooks authenticated via `X-Webhook-Secret` or HMAC shared secret header. |
| **Information Leakage** | PII exposed in application logs | Log messages record only UUIDs, record counts, and high-level rejection reasons. Full email addresses and income figures are excluded from logs. |
| **Outbound Email Safety** | Mass email dispatch to sample applicant emails | Hardware-level `DELIVERY_MODE=test` guardrail overrides recipient to verified developer test inbox allowlist. |

---

## 3. Critical Email Safety Architecture

A primary operational hazard in financial systems is the accidental dispatch of testing messages to real customer email addresses contained in staging or sample datasets.

### Enforced Guardrails:
1. **Default Test Mode**: The system boots with `DELIVERY_MODE=test` and `ALLOW_REAL_RECIPIENTS=false`.
2. **Strict Recipient Resolution**:
   ```python
   def resolve_recipient_email(self, user_csv_email: str) -> str:
       if self.settings.DELIVERY_MODE != "production" or not self.settings.ALLOW_REAL_RECIPIENTS:
           test_recipients = self.settings.test_recipient_list
           if not test_recipients:
               raise NotificationSafetyError("TEST_EMAIL_RECIPIENTS is empty.")
           return test_recipients[0]
   ```
3. **Fail-Safe Circuit Breaker**: If `TEST_EMAIL_RECIPIENTS` is empty in test mode, the notification dispatcher throws `NotificationSafetyError` and records a blocked audit record rather than falling back to the applicant's address.

---

## 4. AWS Infrastructure Hardening

- **Least-Privilege IAM**: Roles are scoped strictly to specific resource ARNs (`arn:aws:s3:::loan-eligibility-uploads-*/*`, `arn:aws:sqs:*:*:loan-ingestion-queue-*`). Wildcard actions (`*`) on resources are strictly forbidden.
- **RDS Isolation**: In AWS production deployment, RDS PostgreSQL is placed inside private VPC subnets with no public IP allocation. Security groups restrict inbound port 5432 exclusively to the Lambda security group and the container worker security group.
- **Secrets Management**: Database credentials and webhook secrets are retrieved at runtime via AWS Systems Manager (SSM) Parameter Store or AWS Secrets Manager. No cleartext secrets exist in repositories or environment templates.

---

## 5. Data Retention & Privacy Compliance

- **Uploaded CSV Storage**: S3 lifecycle rules automatically delete raw upload files 30 days after processing.
- **Incomplete Multipart Uploads**: Aborted automatically after 7 days to eliminate storage accumulation.
- **Audit Logging**: Audit records in `notifications` and `rejected_rows` maintain operational traceability while anonymizing sensitive applicant fields.
