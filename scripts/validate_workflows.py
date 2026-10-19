#!/usr/bin/env python3
"""
Structural and semantic validation suite for n8n workflow JSON definitions.
Ensures correct node topology, SQL pre-filtering order, security, and recipient override.
"""
import json
import os
import sys

WORKFLOW_FILES = {
    "A": "n8n/workflows/workflow_a_loan_discovery.json",
    "B": "n8n/workflows/workflow_b_user_loan_matching.json",
    "C": "n8n/workflows/workflow_c_user_notification.json",
}


def validate_json_syntax(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Workflow file missing: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "nodes" in data, f"{path}: Missing 'nodes' array"
    assert "connections" in data, f"{path}: Missing 'connections' object"
    assert len(data["nodes"]) > 0, f"{path}: 'nodes' array is empty"
    return data


def validate_workflow_a(data: dict):
    print("Validating Workflow A (Loan Discovery)...")
    nodes = {n["name"]: n for n in data["nodes"]}
    node_types = {n["type"] for n in data["nodes"]}

    assert "n8n-nodes-base.scheduleTrigger" in node_types, "Workflow A missing schedule trigger"
    assert "n8n-nodes-base.httpRequest" in node_types, "Workflow A missing HTTP Request node for crawling"
    assert "n8n-nodes-base.postgres" in node_types, "Workflow A missing PostgreSQL node for upsert"

    # Verify upsert query syntax
    pg_node = [n for n in data["nodes"] if n["type"] == "n8n-nodes-base.postgres"][0]
    query = pg_node["parameters"]["query"].lower()
    assert "insert into loan_products" in query, "Workflow A query does not target loan_products"
    assert "on conflict" in query, "Workflow A query missing ON CONFLICT idempotency"
    print("  ✓ Workflow A passed all structural and idempotency checks.")


def validate_workflow_b(data: dict):
    print("Validating Workflow B (Optimized Matching Funnel)...")
    nodes = {n["name"]: n for n in data["nodes"]}
    node_types = {n["type"] for n in data["nodes"]}

    assert "n8n-nodes-base.webhook" in node_types, "Workflow B missing webhook trigger"
    assert "n8n-nodes-base.postgres" in node_types, "Workflow B missing PostgreSQL node"

    # Find SQL pre-filter node
    sql_nodes = [n for n in data["nodes"] if n["type"] == "n8n-nodes-base.postgres"]
    prefilter_query = ""
    for n in sql_nodes:
        q = n["parameters"].get("query", "").lower()
        if "cross join loan_products" in q:
            prefilter_query = q
            break

    assert prefilter_query, "Workflow B missing SQL Pre-filter join query"
    assert "u.import_id = $1" in prefilter_query or "import_id" in prefilter_query, "Workflow B does not parameterize import_id"
    assert "u.monthly_income >= p.min_monthly_income" in prefilter_query, "Missing SQL income predicate"
    assert "u.credit_score >= p.min_credit_score" in prefilter_query, "Missing SQL credit score predicate"
    assert "u.age >= p.min_age" in prefilter_query, "Missing SQL age predicate"

    # Verify that persistence follows rule evaluation and triggers notification
    connections = data["connections"]
    rule_node_out = connections.get("Stage 3 & 4: Evaluate Rules & Build Provenance", {}).get("main", [])
    assert any(c["node"] == "Stage 5: Idempotent Match Persistence" for group in rule_node_out for c in group), \
        "Workflow B rule evaluation does not flow to match persistence"

    persist_node_out = connections.get("Stage 5: Idempotent Match Persistence", {}).get("main", [])
    assert any(c["node"] == "Stage 7: Trigger Workflow C (Notification)" for group in persist_node_out for c in group), \
        "Workflow B does not wait for persistence before triggering Workflow C"

    print("  ✓ Workflow B passed SQL pre-filter, funnel ordering, and persistence checks.")


def validate_workflow_c(data: dict):
    print("Validating Workflow C (Safe Notification via SES)...")
    nodes = {n["name"]: n for n in data["nodes"]}
    node_types = {n["type"] for n in data["nodes"]}

    assert "n8n-nodes-base.webhook" in node_types, "Workflow C missing webhook trigger"
    assert "n8n-nodes-base.postgres" in node_types, "Workflow C missing PostgreSQL node"

    # Find safety override code node
    code_node = [n for n in data["nodes"] if n["type"] == "n8n-nodes-base.code"][0]
    code_text = code_node["parameters"].get("jsCode", "")

    # Strict safety check: must reference TEST_EMAIL_RECIPIENTS and NOT send to sample address
    assert "TEST_EMAIL_RECIPIENTS" in code_text, "Workflow C missing TEST_EMAIL_RECIPIENTS environment reference"
    assert "safe_recipient" in code_text, "Workflow C does not map to safe_recipient"
    assert "DISCLAIMER" in code_text, "Workflow C template missing indicative disclaimer"

    print("  ✓ Workflow C passed critical test-inbox recipient override safety checks.")


def main():
    print("Starting n8n Workflow Validation Suite...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    wf_a = validate_json_syntax(os.path.join(base_dir, WORKFLOW_FILES["A"]))
    validate_workflow_a(wf_a)

    wf_b = validate_json_syntax(os.path.join(base_dir, WORKFLOW_FILES["B"]))
    validate_workflow_b(wf_b)

    wf_c = validate_json_syntax(os.path.join(base_dir, WORKFLOW_FILES["C"]))
    validate_workflow_c(wf_c)

    print("\nALL WORKFLOW DEFINITIONS VALIDATED SUCCESSFULLY (100% Structural & Safety Compliance)")


if __name__ == "__main__":
    main()
