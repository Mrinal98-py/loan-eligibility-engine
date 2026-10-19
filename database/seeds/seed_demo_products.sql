-- Seed Data: Verified Personal Loan Products with Provenance & Clear Criteria
INSERT INTO loan_products (
    id, source_name, source_url, product_name, product_type,
    interest_rate_min, interest_rate_max, min_monthly_income, min_credit_score,
    min_age, max_age, eligible_employment_statuses,
    eligibility_criteria_raw, eligibility_evidence, is_active, verified_at
) VALUES
(
    'a1111111-1111-1111-1111-111111111111',
    'HDFC Bank',
    'https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan',
    'HDFC Bank Personal Loan for Salaried',
    'Personal Loan',
    10.50, 21.00, 25000.00, 720, 21, 60,
    '["Salaried"]'::jsonb,
    'Salaried employees aged 21-60 with net monthly income >= Rs 25,000 and credit score >= 720',
    '{"income_evidence": "Published net monthly income >= 25,000", "score_evidence": "Preferred CIBIL score 720+", "age_evidence": "Min 21, Max 60 at maturity"}'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
),
(
    'b2222222-2222-2222-2222-222222222222',
    'State Bank of India',
    'https://sbi.co.in/web/personal-banking/loans/personal-loans/xpress-credit',
    'SBI Xpress Credit Personal Loan',
    'Personal Loan',
    11.15, 14.30, 30000.00, 700, 21, 58,
    '["Salaried"]'::jsonb,
    'Salaried employees earning >= Rs 30,000 with CIBIL score >= 700',
    '{"income_evidence": "Minimum net monthly income Rs 30,000", "score_evidence": "Minimum credit score 700 required"}'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
),
(
    'c3333333-3333-3333-3333-333333333333',
    'ICICI Bank',
    'https://www.icicibank.com/personal-banking/loans/personal-loan',
    'ICICI Bank Flexible Personal Loan',
    'Personal Loan',
    10.80, 16.50, 35000.00, 700, 23, 58,
    '["Salaried", "Self-Employed"]'::jsonb,
    'Salaried and self-employed professionals with minimum monthly income Rs 35,000 and credit score 700+',
    '{"income_evidence": "Minimum net take-home salary Rs 35,000 p.m.", "score_evidence": "CIBIL score 700 or above"}'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
),
(
    'd4444444-4444-4444-4444-444444444444',
    'Bajaj Finserv',
    'https://www.bajajfinserv.in/personal-loan',
    'Bajaj Finserv Instant Personal Loan',
    'Personal Loan',
    11.00, 22.00, 35000.00, 685, 21, 68,
    '["Salaried", "Business", "Self-Employed"]'::jsonb,
    'Indian citizens aged 21-68, salaried or self-employed, monthly salary >= Rs 35,000, credit score >= 685',
    '{"income_evidence": "Monthly salary starting from Rs 35,000", "score_evidence": "CIBIL score of 685 or higher"}'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
),
(
    'e5555555-5555-5555-5555-555555555555',
    'Axis Bank',
    'https://www.axisbank.com/retail/loans/personal-loan',
    'Axis Bank Business & Self-Employed Loan',
    'Personal Loan',
    12.00, 21.00, 50000.00, 725, 24, 65,
    '["Self-Employed", "Business"]'::jsonb,
    'Self-employed individuals and business owners with declared monthly income >= Rs 50,000 and credit score >= 725',
    '{"income_evidence": "Minimum monthly income Rs 50,000 based on ITR", "score_evidence": "Score >= 725"}'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
),
(
    'f6666666-6666-6666-6666-666666666666',
    'Kotak Mahindra Bank',
    'https://www.kotak.com/en/personal-banking/loans/personal-loan.html',
    'Kotak Premium Personal Loan',
    'Personal Loan',
    10.99, 18.00, 40000.00, 750, 21, 60,
    '["Salaried"]'::jsonb,
    'Salaried corporate employees with net income >= Rs 40,000 and credit score >= 750',
    '{"income_evidence": "Minimum net monthly salary Rs 40,000", "score_evidence": "Credit score 750+"}'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (source_url, product_name) DO UPDATE SET
    interest_rate_min = EXCLUDED.interest_rate_min,
    interest_rate_max = EXCLUDED.interest_rate_max,
    min_monthly_income = EXCLUDED.min_monthly_income,
    min_credit_score = EXCLUDED.min_credit_score,
    min_age = EXCLUDED.min_age,
    max_age = EXCLUDED.max_age,
    eligible_employment_statuses = EXCLUDED.eligible_employment_statuses,
    eligibility_criteria_raw = EXCLUDED.eligibility_criteria_raw,
    eligibility_evidence = EXCLUDED.eligibility_evidence,
    is_active = EXCLUDED.is_active,
    updated_at = CURRENT_TIMESTAMP;
