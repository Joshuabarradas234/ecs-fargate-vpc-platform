"""
Cost-audit tool — entry point.

Fetches live data from AWS via Boto3, runs the pure decision logic in
checks.py, prints a readable report, and optionally writes JSON.

SAFETY: this tool only *identifies* opportunities. It never deletes or
modifies anything. Remediation is a human decision.

Usage:
    python auditor.py                 # print report for the default region
    python auditor.py --region eu-west-2
    python auditor.py --json report.json
"""

import argparse
import json
import sys
from typing import Optional

import checks


def _client(service: str, region: Optional[str]):
    import boto3  # imported here so checks.py stays import-free of AWS

    return boto3.client(service, region_name=region) if region else boto3.client(service)


def gather_findings(region: Optional[str] = None) -> list:
    """Call AWS, feed the responses into the pure checks, return all findings."""
    ec2 = _client("ec2", region)
    rds = _client("rds", region)

    findings: list = []

    # Unattached EBS volumes.
    volumes = ec2.describe_volumes().get("Volumes", [])
    findings += checks.find_unattached_volumes(volumes)

    # Idle Elastic IPs.
    addresses = ec2.describe_addresses().get("Addresses", [])
    findings += checks.find_idle_elastic_ips(addresses)

    # NAT gateways.
    nats = ec2.describe_nat_gateways().get("NatGateways", [])
    findings += checks.summarise_nat_gateways(nats)

    # Untagged resources: check EC2 instances (extendable to more types).
    reservations = ec2.describe_instances().get("Reservations", [])
    instances = []
    for res in reservations:
        for inst in res.get("Instances", []):
            instances.append(
                {
                    "id": inst.get("InstanceId"),
                    "type": "ec2_instance",
                    "Tags": inst.get("Tags", []),
                }
            )
    findings += checks.find_untagged_resources(instances)

    # RDS instances (class + Multi-AZ).
    db_instances = rds.describe_db_instances().get("DBInstances", [])
    findings += checks.summarise_rds_instances(db_instances)

    return findings


def print_report(findings: list) -> None:
    """Print a readable table of findings and the estimated monthly total."""
    if not findings:
        print("No findings. Nothing flagged in this region.")
        return

    header = f"{'RESOURCE':<28} {'TYPE':<14} {'ISSUE':<34} {'~$/mo':>8}"
    print(header)
    print("-" * len(header))
    for f in findings:
        print(
            f"{f['resource_id']:<28.28} "
            f"{f['resource_type']:<14.14} "
            f"{f['issue']:<34.34} "
            f"{f['monthly_cost_usd']:>8.2f}"
        )
        if f.get("detail"):
            print(f"    ↳ {f['detail']}")

    total = checks.total_estimated_waste(findings)
    print("-" * len(header))
    print(f"Estimated addressable monthly cost: ~${total:.2f} USD")
    print("(estimates for prioritisation only — not a billing figure)")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="AWS cost-optimisation auditor (read-only).")
    parser.add_argument("--region", help="AWS region (defaults to your configured region).")
    parser.add_argument("--json", metavar="PATH", help="Also write findings as JSON to PATH.")
    args = parser.parse_args(argv)

    try:
        findings = gather_findings(region=args.region)
    except Exception as exc:  # network/creds/permission errors surface clearly
        print(f"Error gathering data from AWS: {exc}", file=sys.stderr)
        print("Check your AWS credentials and permissions (read-only is enough).", file=sys.stderr)
        return 1

    print_report(findings)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {"findings": findings, "estimated_monthly_usd": checks.total_estimated_waste(findings)},
                fh,
                indent=2,
            )
        print(f"\nJSON written to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
