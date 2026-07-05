"""Tests for the plan parser. Uses tmp_path to write small plan JSONs per case."""

import json

from iac_sentinel.plan_parser import parse_plan


def _write_plan(tmp_path, resource_changes: list) -> str:
    """Write a minimal plan JSON to a temp file and return its path."""
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"resource_changes": resource_changes}), encoding="utf-8")
    return str(path)


def test_noop_is_dropped(tmp_path):
    plan = _write_plan(
        tmp_path,
        [
            {"address": "a.x", "type": "aws_s3_bucket",
             "change": {"actions": ["no-op"], "after": {"bucket": "x"}}},
            {"address": "a.y", "type": "aws_s3_bucket",
             "change": {"actions": ["create"], "after": {"bucket": "y"}}},
        ],
    )
    changes = parse_plan(plan)
    # Only the create survives; the no-op is noise and must be filtered out.
    assert [c.address for c in changes] == ["a.y"]


def test_delete_after_is_normalized_to_empty_dict(tmp_path):
    # A pure delete has after=null; parser must normalize it to {} (no None downstream).
    plan = _write_plan(
        tmp_path,
        [{"address": "db.main", "type": "aws_db_instance",
          "change": {"actions": ["delete"], "after": None}}],
    )
    changes = parse_plan(plan)
    assert len(changes) == 1
    assert changes[0].after == {}
    assert changes[0].action == "delete"


def test_replace_is_kept(tmp_path):
    # replace = ["delete", "create"] must be reviewed, not dropped.
    plan = _write_plan(
        tmp_path,
        [{"address": "sg.web", "type": "aws_security_group",
          "change": {"actions": ["delete", "create"], "after": {"name": "sg"}}}],
    )
    changes = parse_plan(plan)
    assert len(changes) == 1
    assert changes[0].action == "delete"  # first reviewable action is used as the label
