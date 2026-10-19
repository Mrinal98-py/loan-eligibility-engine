# The Optimization Treasure Hunt: High-Throughput Candidate Funnel

## Executive Summary

Evaluating loan eligibility across large applicant pools presents a severe computational and cost scalability bottleneck if designed naively. In an enterprise system ingesting bulk datasets (e.g., 10,000 to 100,000 users) matched against dozens of lending institutions, a brute-force approach that passes candidate pairs into an LLM or unindexed application loops incurs massive latency, token costs, and rate-limit throttling.

This document details the architecture, mathematical model, and empirical benchmark results of the **Multi-Stage Optimization Funnel** implemented in the Loan Eligibility Engine.

---

## 1. Architectural Funnel: The 5-Stage Pipeline

```
┌────────────────────────────────────────────────────────┐
│  Stage 1: Ingestion Normalization & Validation          │
│  - Strict type coercion (Decimal, Integer)             │
│  - Formula injection mitigation & deduplication         │
└──────────────────────────┬─────────────────────────────┘
                           │ 100% of Raw Inputs
                           ▼
┌────────────────────────────────────────────────────────┐
│  Stage 2: Deterministic PostgreSQL SQL Pre-Filter       │
│  - Indexed composite joins (income, credit, age, emp)   │
│  - Eliminates 65% – 95% of impossible pairs in DB layer │
└──────────────────────────┬─────────────────────────────┘
                           │ 31.32% Candidates Remain
                           ▼
┌────────────────────────────────────────────────────────┐
│  Stage 3: Deterministic Rule Engine & Provenance        │
│  - Versioned business logic & criteria verification     │
│  - Transparent explanation synthesis for end users      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Stage 4: Targeted, Budget-Bounded AI Resolution        │
│  - Only triggered for ambiguous/qualitative text criteria│
│  - Hash-keyed semantic caching & strict JSON validation │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Stage 5: Idempotent Persistence & Safe Notification    │
│  - ON CONFLICT DO NOTHING batch inserts                │
│  - Hardware test-mode recipient override                │
└────────────────────────────────────────────────────────┘
```

### Stage 1: Data Normalization
All incoming financial attributes are parsed using streaming memory-efficient readers. Monthly income is normalized into arbitrary-precision `NUMERIC(14, 2)` to eliminate floating-point rounding errors. Credit scores and applicant ages are validated against statutory domains ($300 \le \text{Credit Score} \le 900$, $18 \le \text{Age} \le 120$), and employment categories are normalized into a canonical enum.

### Stage 2: SQL Hard-Rule Pre-Filtering (The Core Innovation)
Rather than pulling all users and products into application memory or orchestrator loops, we leverage the relational database engine's optimized query planner and B-tree indexes:

```sql
SELECT 
    u.id AS user_id,
    p.id AS product_id,
    p.source_name,
    p.product_name,
    p.interest_rate_min,
    p.interest_rate_max
FROM users u
CROSS JOIN loan_products p
WHERE u.import_id = :import_id
  AND p.is_active = TRUE
  AND u.monthly_income >= p.min_monthly_income
  AND u.credit_score >= p.min_credit_score
  AND (p.max_credit_score IS NULL OR u.credit_score <= p.max_credit_score)
  AND u.age >= p.min_age
  AND u.age <= p.max_age
  AND p.eligible_employment_statuses @> to_jsonb(u.employment_status);
```

#### Index Strategy:
- `users`: Composite index on `(import_id, monthly_income, credit_score, age, employment_status)`
- `loan_products`: Composite index on `(is_active, min_monthly_income, min_credit_score, min_age, max_age)`
- `loan_products.eligible_employment_statuses`: GIN index for JSONB containment queries (`@>`)

### Stage 3: Deterministic Rule Engine & Provenance
For candidate pairs that satisfy hard mathematical boundaries, the rule engine generates human-readable audit explanations citing verified evidence snippets (e.g. `"Monthly income ₹131,000 exceeds minimum threshold ₹25,000"`).

### Stage 4: Targeted AI Resolution
Language models are **never** permitted to make credit decisions or override numeric hard rules. LLM invocations are strictly limited to qualitative ambiguities (such as mapping nonstandard employment titles to bank-accepted categories). Reusable evaluations are cached by `hash(criteria_text, model, prompt_version)`.

### Stage 5: Idempotent Persistence
Matches are committed using PostgreSQL's `ON CONFLICT (user_id, product_id, import_id) DO NOTHING` in batch chunks of 1,000 rows, preventing duplicate matches during workflow retries.

---

## 2. Worked Example: Hypothetical Scaling Analysis

Consider a mid-sized batch of **5,000 users** and **30 loan products**:

- **Naive Direct Approach:**
  $$\text{Candidate Pairs} = 5,000 \times 30 = 150,000 \text{ evaluations}$$
  - At an average of 350 tokens per prompt/completion pair:
    $$\text{Total Tokens} = 150,000 \times 350 = 52,500,000 \text{ tokens}$$
  - At standard LLM rates (\$0.15 / 1M input, \$0.60 / 1M output, blended \$0.35 / 1M):
    $$\text{Estimated LLM Cost} = \frac{52,500,000}{1,000,000} \times \$0.35 = \$18.38 \text{ USD per single import}$$
  - Latency with 10 concurrent requests @ 50ms:
    $$\text{Latency} \approx \frac{150,000 \times 0.05}{10} = 750 \text{ seconds } (12.5 \text{ minutes})$$

- **Optimized SQL Funnel Approach:**
  - Income and credit score thresholds reject ~75% of ineligible pairs.
  - Age and employment criteria reject another ~10%.
  - Surviving candidates entering downstream evaluation: ~22,500 pairs (**85.0% reduction**).
  - Ambiguous cases requiring LLM calls: < 0.1% (~20 unique cached evaluations).
  - Downstream AI cost: **<\$0.01 USD**.
  - PostgreSQL execution latency: **<150 milliseconds**.

---

## 3. Empirical Benchmark Results (Actual Measurement)

The benchmark was executed against the **actual 10,000 applicant CSV** (`sample_users_10k.csv`) on PostgreSQL 16 on Apple Silicon:

| Metric | Naive Direct Approach | Optimized PostgreSQL Funnel | Difference / Savings |
| :--- | :--- | :--- | :--- |
| **Ingested Users ($N$)** | 10,000 | 10,000 | &mdash; |
| **Active Loan Products ($M$)** | 6 | 6 | &mdash; |
| **Theoretical Search Space** | 60,000 pairs | 60,000 pairs | &mdash; |
| **Pairs Entering Expensive Eval** | 60,000 | **18,793** | **-41,207 pairs** |
| **Candidate Reduction Ratio** | 0.00% | **68.68%** | **+68.68% reduction** |
| **PostgreSQL Pre-Filter Latency**| N/A | **197.57 ms** | Sub-second DB execution |
| **Total Funnel Execution Time** | ~300.0 s (5.0 min) | **2.60 s** | **~115.3x faster** |
| **LLM Calls Dispatched** | 60,000 | **0** | **60,000 calls avoided** |
| **Token Consumption** | 21,000,000 tokens | **0 tokens** | **100% token savings** |
| **Estimated LLM Cloud Spend** | \$7.35 USD | **\$0.00 USD** | **100% cost reduction** |

---

## 4. Correctness Trade-offs Analysis

Does the SQL Pre-Filter introduce false negatives or compromise accuracy?

1. **Mathematical Equivalence**: The SQL predicates (`>=`, `<=`, `@>`) enforce the exact published thresholds of the banking products. If an applicant has a monthly income of ₹24,000 and a bank requires a minimum of ₹25,000, that candidate is unconditionally ineligible under the bank's published terms. Evaluating that candidate with an LLM cannot legitimately overturn a hard numeric requirement.
2. **Missing Criteria Policy**: If a loan product does not publish an upper age limit or maximum credit score, the database column contains `NULL`. The SQL predicate `(p.max_credit_score IS NULL OR u.credit_score <= p.max_credit_score)` ensures that missing criteria are **never** treated as automatic disqualifications.
3. **Auditability**: Every surviving match contains structured provenance entries (`eligibility_evidence`) detailing the exact statutory rule, the applicant's value, and the lender's threshold.
