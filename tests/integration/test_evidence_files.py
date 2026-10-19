"""The committed execution evidence must be reproducible and pass the independent checker."""

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "competition" / "evidence"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = _load("verify_evidence")


def _committed(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_committed_logs_pass_the_independent_check():
    for name in verify.DEFAULT_LOGS:
        assert verify.check_log(_committed(name)) == [], name


def test_committed_evidence_matches_a_fresh_run():
    demo = _load("demo_15_steps")
    steps, log = demo.run()
    assert demo.render(steps) == (EVIDENCE / "demo_15_steps.md").read_text(encoding="utf-8")
    assert json.loads(json.dumps(log, default=str)) == _committed("demo_15_steps.json")

    transcript, log = _load("demo_offline").run()
    assert transcript == (EVIDENCE / "offline_demo_transcript.md").read_text(encoding="utf-8")
    assert json.loads(json.dumps(log)) == _committed("sandbox_operation_log.json")


def test_checker_detects_an_edited_entry():
    log = _committed("demo_15_steps.json")
    edited = copy.deepcopy(log)
    edited["audit_log"][1]["payload"]["strategy"] = "GOAL_FIRST"
    assert any("hash does not match" in p for p in verify.check_log(edited))


def test_checker_detects_a_deleted_entry():
    log = _committed("demo_15_steps.json")
    del log["audit_log"][2]
    assert any("does not link" in p for p in verify.check_log(log))


def test_checker_detects_an_agent_approval_and_a_second_execution():
    log = _committed("demo_15_steps.json")
    approval = next(e for e in log["audit_log"] if e["action"] == "PLAN_APPROVED")
    approval["actor"] = "AGENT"
    execution = next(e for e in log["audit_log"] if e["action"] == "PLAN_EXECUTED")
    log["audit_log"].append(copy.deepcopy(execution))
    problems = verify.check_log(log)
    assert any("only the user may" in p for p in problems)
    assert any("used twice" in p for p in problems)
