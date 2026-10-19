#!/usr/bin/env python3
"""
Generate synthetic bulk user datasets matching the schema of the assignment.
Includes options for clean benchmark data or intentional anomaly testing.
"""
import argparse
import csv
import random
import uuid

FIRST_NAMES = ["Dhruv", "Tara", "Ananya", "Shaurya", "Ishaan", "Isha", "Aditya", "Kabir", "Advik", "Zoya", "Aanya", "Sana", "Diya", "Vivaan", "Anika", "Rohan", "Meera", "Karan"]
LAST_NAMES = ["Iyengar", "Khan", "Pandey", "Iyer", "Trivedi", "Chauhan", "Kapoor", "Roy", "Soni", "Gupta", "Desai", "Agarwal", "Chopra", "Reddy", "Joshi", "Thakur", "Sharma"]
EMPLOYMENT_TYPES = ["Salaried", "Self-Employed", "Business"]


def generate_users(count: int, output_file: str, inject_anomalies: bool = False):
    print(f"Generating {count} synthetic user rows to {output_file}...")
    
    rows = []
    seen_ids = set()

    for i in range(count):
        uid = str(uuid.uuid4())
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        name = f"{fname} {lname}"
        email = f"{fname.lower()}.{lname.lower()}{i}@example.com"
        
        # Realistic Indian salary & credit score distributions
        income = random.choice([25000, 32000, 45000, 55000, 68000, 85000, 110000, 135000, 160000])
        credit = random.randint(620, 810)
        emp = random.choice(EMPLOYMENT_TYPES)
        age = random.randint(22, 58)

        # Inject anomalies on a small percentage if requested
        if inject_anomalies and i % 50 == 0:
            anomaly_type = i % 4
            if anomaly_type == 0:
                income = -5000  # Negative income
            elif anomaly_type == 1:
                credit = 250    # Sub-300 credit score
            elif anomaly_type == 2:
                email = "invalid-email-format"
            elif anomaly_type == 3:
                age = 15        # Underage

        rows.append({
            "user_id": uid,
            "name": name,
            "email": email,
            "monthly_income": income,
            "credit_score": credit,
            "employment_status": emp,
            "age": age,
        })

    # Add 1 duplicate if anomalies enabled
    if inject_anomalies and count > 10:
        dup = dict(rows[0])
        rows.append(dup)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "name", "email", "monthly_income", "credit_score", "employment_status", "age"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Successfully generated {len(rows)} records in {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic user loan applicant CSV")
    parser.add_argument("--count", type=int, default=1000, help="Number of records to generate")
    parser.add_argument("--out", type=str, default="n8n/fixtures/sample_users_small.csv", help="Output path")
    parser.add_argument("--anomalies", action="store_true", help="Inject invalid rows to test rejection engine")
    args = parser.parse_args()

    generate_users(args.count, args.out, args.anomalies)
