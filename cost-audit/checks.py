"""
Pure cost-optimisation decision logic.

No AWS calls here — every function takes plain Python data (lists of dicts,
shaped like the AWS API responses) and returns findings. This is the pattern
that makes the logic unit-testable without AWS: the Boto3 layer (auditor.py)
fetches the data, then hands it to these functions.

Each finding is a dict: {resource_id, resource_type, issue, monthly_cost_usd, detail}.
`monthly_cost_usd` is an ESTIMATE for prioritisation, not a billing figure.
"""

from typing import Optional

# Rough, region-agnostic monthly cost estimates (USD) used only to help
# prioritise findings. Real costs vary by region and usage; these are
# deliberately conservative round numbers and documented as estimates.
EBS_GP3_PER_GB_MONTH = 0.08
EIP_IDLE_PER_MONTH = 3.60      # ~ $0.005/hr for an unassociated EIP
NAT_GATEWAY_PER_MONTH = 32.40  # ~ $0.045/hr fixed (excl. data processing)

REQUIRED_TAGS = ("Project", "Environment")


def _tags_to_dict(tags: Optional[list]) -> dict:
    """Normalise an AWS-style [{'Key':..,'Value':..}] list into a dict."""
    if not tags:
        return {}
    return {t.get("Key"): t.get("Value") for t in tags if "Key" in t}


def find_unattached_volumes(volumes: list) -> list:
    """
    Flag EBS volumes with status 'available' (attached to nothing).

    `volumes` items look like: {"VolumeId": "vol-…", "State": "available",
    "Size": 30}  (Size in GiB).
    """
    findings = []
    for v in volumes:
        if v.get("State") == "available":
            size = v.get("Size", 0)
            findings.append(
                {
                    "resource_id": v.get("VolumeId", "unknown"),
                    "resource_type": "ebs_volume",
                    "issue": "unattached (status=available)",
                    "monthly_cost_usd": round(size * EBS_GP3_PER_GB_MONTH, 2),
                    "detail": f"{size} GiB not attached to any instance",
                }
            )
    return findings


def find_idle_elastic_ips(addresses: list) -> list:
    """
    Flag Elastic IPs with no association (charged while unused).

    `addresses` items look like: {"PublicIp": "1.2.3.4", "AllocationId": "eipalloc-…"}
    with no "AssociationId" / "InstanceId" / "NetworkInterfaceId" when idle.
    """
    findings = []
    for a in addresses:
        associated = any(
            a.get(k) for k in ("AssociationId", "InstanceId", "NetworkInterfaceId")
        )
        if not associated:
            findings.append(
                {
                    "resource_id": a.get("AllocationId") or a.get("PublicIp", "unknown"),
                    "resource_type": "elastic_ip",
                    "issue": "idle (no association)",
                    "monthly_cost_usd": EIP_IDLE_PER_MONTH,
                    "detail": f"{a.get('PublicIp', 'unknown')} not associated",
                }
            )
    return findings


def summarise_nat_gateways(nat_gateways: list) -> list:
    """
    Report each available NAT gateway and its fixed monthly cost.

    NAT is a classic ECS/VPC cost sink, so we always surface it (informational),
    not just when 'idle' — you can't easily tell 'idle' from the API alone.

    Items look like: {"NatGatewayId": "nat-…", "State": "available"}.
    """
    findings = []
    for n in nat_gateways:
        if n.get("State") in ("available", "pending"):
            findings.append(
                {
                    "resource_id": n.get("NatGatewayId", "unknown"),
                    "resource_type": "nat_gateway",
                    "issue": "fixed hourly cost (review if still needed)",
                    "monthly_cost_usd": NAT_GATEWAY_PER_MONTH,
                    "detail": "NAT gateways bill ~$0.045/hr plus data processing",
                }
            )
    return findings


def find_untagged_resources(resources: list) -> list:
    """
    Flag resources missing any REQUIRED_TAGS (cost-allocation hygiene).

    `resources` items look like:
      {"id": "i-…", "type": "ec2_instance", "Tags": [{"Key":..,"Value":..}]}
    """
    findings = []
    for r in resources:
        tags = _tags_to_dict(r.get("Tags"))
        missing = [t for t in REQUIRED_TAGS if t not in tags]
        if missing:
            findings.append(
                {
                    "resource_id": r.get("id", "unknown"),
                    "resource_type": r.get("type", "unknown"),
                    "issue": "missing required tags",
                    "monthly_cost_usd": 0.0,
                    "detail": f"missing: {', '.join(missing)}",
                }
            )
    return findings


def summarise_rds_instances(instances: list) -> list:
    """
    Report RDS instance class and Multi-AZ (both cost drivers).

    Items look like: {"DBInstanceIdentifier": "…", "DBInstanceClass":
    "db.t3.micro", "MultiAZ": false}.
    """
    findings = []
    for db in instances:
        multi_az = bool(db.get("MultiAZ"))
        issue = "Multi-AZ enabled (~2x cost)" if multi_az else "single-AZ (cost-optimised)"
        findings.append(
            {
                "resource_id": db.get("DBInstanceIdentifier", "unknown"),
                "resource_type": "rds_instance",
                "issue": issue,
                "monthly_cost_usd": 0.0,  # class-dependent; reported, not estimated
                "detail": f"class={db.get('DBInstanceClass', 'unknown')}, multi_az={multi_az}",
            }
        )
    return findings


def total_estimated_waste(findings: list) -> float:
    """Sum the monthly_cost_usd across findings (the prioritisation number)."""
    return round(sum(f.get("monthly_cost_usd", 0.0) for f in findings), 2)
