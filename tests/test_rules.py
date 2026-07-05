"""Tests for the deterministic safety net. Pure functions -> fast, no API, no network."""

from iac_sentinel.plan_parser import ResourceChange
from iac_sentinel.rules import HIGH_COUNT_THRESHOLD, apply_rules


def _change(type_: str, after: dict, action: str = "create") -> ResourceChange:
    """Small helper to build a ResourceChange without going through JSON."""
    return ResourceChange(address=f"{type_}.test", type=type_, action=action, after=after)


# --- Open ingress rule -------------------------------------------------------

def test_open_ingress_fires_on_world_open_sg():
    change = _change(
        "aws_security_group",
        {"ingress": [{"from_port": 22, "cidr_blocks": ["0.0.0.0/0"]}]},
    )
    findings = apply_rules([change])
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_open_ingress_silent_on_restricted_sg():
    # Negative case: a restricted CIDR must NOT trigger a finding (no false positive).
    change = _change(
        "aws_security_group",
        {"ingress": [{"from_port": 22, "cidr_blocks": ["10.0.0.0/8"]}]},
    )
    assert apply_rules([change]) == []


# --- Unencrypted storage rule ------------------------------------------------

def test_unencrypted_storage_fires():
    change = _change("aws_db_instance", {"storage_encrypted": False})
    assert len(apply_rules([change])) == 1


def test_encrypted_storage_silent():
    change = _change("aws_db_instance", {"storage_encrypted": True})
    assert apply_rules([change]) == []


# --- Expensive compute rule (boundary tests) --------------------------------

def test_expensive_instance_type_fires():
    change = _change("aws_instance", {"instance_type": "p4d.24xlarge", "count": 1})
    assert len(apply_rules([change])) == 1


def test_high_count_at_threshold_fires():
    # Boundary: exactly at the threshold should fire.
    change = _change("aws_instance", {"instance_type": "t3.micro", "count": HIGH_COUNT_THRESHOLD})
    assert len(apply_rules([change])) == 1


def test_count_below_threshold_silent():
    # Boundary: one below the threshold must stay silent (avoid alert fatigue).
    change = _change("aws_instance", {"instance_type": "t3.micro", "count": HIGH_COUNT_THRESHOLD - 1})
    assert apply_rules([change]) == []
