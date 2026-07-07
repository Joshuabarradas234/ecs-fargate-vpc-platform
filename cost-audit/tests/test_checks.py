"""
Unit tests for the pure cost-audit decision logic (checks.py).

No AWS, no Boto3 — every test feeds plain dicts shaped like AWS API
responses and asserts on the findings. Run: pytest cost-audit/tests -q
"""

import os
import sys

# Make checks.py importable when tests run from the repo root or the folder.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import checks


# ---------------------------------------------------------------------------
# Unattached EBS volumes
# ---------------------------------------------------------------------------
def test_flags_only_available_volumes():
    volumes = [
        {"VolumeId": "vol-1", "State": "available", "Size": 30},
        {"VolumeId": "vol-2", "State": "in-use", "Size": 100},
    ]
    findings = checks.find_unattached_volumes(volumes)
    ids = [f["resource_id"] for f in findings]
    assert ids == ["vol-1"]
    assert findings[0]["monthly_cost_usd"] == round(30 * checks.EBS_GP3_PER_GB_MONTH, 2)


def test_no_volumes_no_findings():
    assert checks.find_unattached_volumes([]) == []


# ---------------------------------------------------------------------------
# Idle Elastic IPs
# ---------------------------------------------------------------------------
def test_flags_unassociated_eip():
    addresses = [
        {"PublicIp": "1.1.1.1", "AllocationId": "eipalloc-idle"},
        {"PublicIp": "2.2.2.2", "AllocationId": "eipalloc-used", "AssociationId": "eipassoc-x"},
    ]
    findings = checks.find_idle_elastic_ips(addresses)
    ids = [f["resource_id"] for f in findings]
    assert ids == ["eipalloc-idle"]


def test_eip_with_instance_id_is_not_idle():
    addresses = [{"PublicIp": "3.3.3.3", "AllocationId": "e-1", "InstanceId": "i-123"}]
    assert checks.find_idle_elastic_ips(addresses) == []


# ---------------------------------------------------------------------------
# NAT gateways
# ---------------------------------------------------------------------------
def test_summarises_available_nat_only():
    nats = [
        {"NatGatewayId": "nat-1", "State": "available"},
        {"NatGatewayId": "nat-2", "State": "deleted"},
    ]
    findings = checks.summarise_nat_gateways(nats)
    ids = [f["resource_id"] for f in findings]
    assert ids == ["nat-1"]
    assert findings[0]["monthly_cost_usd"] == checks.NAT_GATEWAY_PER_MONTH


# ---------------------------------------------------------------------------
# Untagged resources
# ---------------------------------------------------------------------------
def test_flags_resource_missing_required_tags():
    resources = [
        {"id": "i-1", "type": "ec2_instance", "Tags": [{"Key": "Project", "Value": "x"}]},  # missing Environment
        {"id": "i-2", "type": "ec2_instance", "Tags": [
            {"Key": "Project", "Value": "x"}, {"Key": "Environment", "Value": "dev"}]},  # complete
    ]
    findings = checks.find_untagged_resources(resources)
    ids = [f["resource_id"] for f in findings]
    assert ids == ["i-1"]
    assert "Environment" in findings[0]["detail"]


def test_resource_with_no_tags_is_flagged():
    resources = [{"id": "i-3", "type": "ec2_instance"}]
    findings = checks.find_untagged_resources(resources)
    assert len(findings) == 1
    assert "Project" in findings[0]["detail"]
    assert "Environment" in findings[0]["detail"]


# ---------------------------------------------------------------------------
# RDS instances
# ---------------------------------------------------------------------------
def test_rds_reports_multi_az_and_class():
    instances = [
        {"DBInstanceIdentifier": "db-1", "DBInstanceClass": "db.t3.micro", "MultiAZ": False},
        {"DBInstanceIdentifier": "db-2", "DBInstanceClass": "db.r5.large", "MultiAZ": True},
    ]
    findings = checks.summarise_rds_instances(instances)
    by_id = {f["resource_id"]: f for f in findings}
    assert "single-AZ" in by_id["db-1"]["issue"]
    assert "Multi-AZ" in by_id["db-2"]["issue"]
    assert "db.t3.micro" in by_id["db-1"]["detail"]


# ---------------------------------------------------------------------------
# Total
# ---------------------------------------------------------------------------
def test_total_estimated_waste_sums_costs():
    findings = [
        {"monthly_cost_usd": 10.0},
        {"monthly_cost_usd": 2.5},
        {"monthly_cost_usd": 0.0},
    ]
    assert checks.total_estimated_waste(findings) == 12.5


def test_total_handles_empty():
    assert checks.total_estimated_waste([]) == 0.0
