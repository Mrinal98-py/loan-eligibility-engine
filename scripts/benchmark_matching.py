#!/usr/bin/env python3
"""
Optimization Treasure Hunt Benchmark:
Quantifies candidate reduction and token/cost savings between
the Naive N x M LLM evaluation vs. the Optimized SQL Pre-Filter Funnel.
"""
import os
import sys
import time
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal
from backend.app.models.base import Import, User, LoanProduct
from backend.app.services.matching_service import MatchingService


def run_benchmark(import_id_str: str = None):
    db = SessionLocal()
    try:
        # 1. Select import
        if import_id_str:
            target_import = db.query(Import).filter(Import.id == UUID(import_id_str)).first()
        else:
            target_import = db.query(Import).filter(Import.status.in_(["PROCESSED", "PARTIAL_REJECTED"])).order_by(Import.created_at.desc()).first()

        if not target_import:
            print("No processed import found in database. Please run an ingestion first.")
            return

        import_id = target_import.id
        print(f"\n================================================================================")
        print(f"  OPTIMIZATION TREASURE HUNT: BENCHMARK REPORT")
        print(f"  Target Import ID: {import_id} ({target_import.original_filename})")
        print(f"================================================================================")

        # 2. Naive Baseline Calculation
        user_count = db.query(User).filter(User.import_id == import_id).count()
        active_products = db.query(LoanProduct).filter(LoanProduct.is_active.is_(True)).count()
        theoretical_pairs = user_count * active_products

        print(f"\n[1. Naive Direct LLM Approach]")
        print(f"  Total Ingested Users (N)     : {user_count:,}")
        print(f"  Active Loan Products (M)     : {active_products:,}")
        print(f"  Theoretical Candidate Pairs  : {theoretical_pairs:,} (N × M evaluations)")
        
        # Hypothetical cost estimates: 350 tokens/pair @ $0.150 per 1M input tokens + $0.600 per 1M output tokens
        avg_tokens_per_call = 350
        naive_total_tokens = theoretical_pairs * avg_tokens_per_call
        naive_est_cost_usd = (naive_total_tokens / 1_000_000) * 0.35  # blended average
        naive_est_duration_sec = theoretical_pairs * 0.05 / 10  # 10 concurrent calls @ 50ms avg
        
        print(f"  Estimated LLM Token Overhead : {naive_total_tokens:,} tokens")
        print(f"  Estimated OpenAI / Gemini Cost: ${naive_est_cost_usd:,.2f} USD")
        print(f"  Estimated Ingestion Latency  : ~{naive_est_duration_sec:,.1f} seconds (~{naive_est_duration_sec/60:,.1f} mins)")

        # 3. Optimized PostgreSQL Funnel Benchmark
        print(f"\n[2. Optimized PostgreSQL Funnel Execution]")
        service = MatchingService(db)

        start_time = time.perf_counter()
        prefiltered_pairs = service.run_sql_prefilter(import_id)
        sql_duration_ms = (time.perf_counter() - start_time) * 1000

        pairs_after_sql = len(prefiltered_pairs)
        reduction_percentage = ((theoretical_pairs - pairs_after_sql) / theoretical_pairs) * 100 if theoretical_pairs > 0 else 0

        # Full funnel execution
        start_full = time.perf_counter()
        metrics = service.execute_matching_funnel(import_id)
        full_duration_ms = (time.perf_counter() - start_full) * 1000

        opt_tokens = metrics.llm_evaluations_performed * avg_tokens_per_call
        opt_cost_usd = (opt_tokens / 1_000_000) * 0.35

        print(f"  SQL Pre-Filter Execution Time: {sql_duration_ms:.2f} ms")
        print(f"  Pairs Surviving SQL Filter   : {pairs_after_sql:,}")
        print(f"  Candidate Pairs Eliminated   : {theoretical_pairs - pairs_after_sql:,}")
        print(f"  Candidate Reduction Ratio    : {reduction_percentage:.2f}%")
        print(f"  Deterministic Matches Found  : {metrics.deterministic_matches_found:,}")
        print(f"  Targeted LLM Calls Made      : {metrics.llm_evaluations_performed:,}")
        print(f"  LLM Calls Safely Avoided     : {metrics.llm_evaluations_avoided:,}")
        print(f"  Optimized Token Consumption  : {opt_tokens:,} tokens")
        print(f"  Optimized LLM Spend          : ${opt_cost_usd:,.4f} USD")
        print(f"  Total Funnel Execution Time  : {full_duration_ms:.2f} ms")

        print(f"\n================================================================================")
        print(f"  SUMMARY COMPARISON")
        print(f"  Candidate Search Space Reduction : {reduction_percentage:.2f}%")
        print(f"  Cost Savings Ratio               : {((naive_est_cost_usd - opt_cost_usd)/naive_est_cost_usd)*100:.2f}%")
        print(f"  Throughput Speedup               : ~{(naive_est_duration_sec * 1000) / max(full_duration_ms, 1):,.1f}x faster")
        print(f"================================================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_benchmark(target)
