"""Check the exported sandbox logs in docs/competition/evidence/ on their own.

This script deliberately does not import `lifecfo`: it re-implements the audit
hash from its definition so that a reviewer can check the evidence files
without trusting the code that wrote them.

For each log it checks:

1. The audit hash chain: the first entry links to the genesis hash (64 zeros),
   every entry links to the one before it, and every hash equals
   SHA-256(prev_hash, ts, actor, action, payload as sorted JSON), joined by newlines.
2. Only the user approved, rejected, or confirmed real events.
3. Every executed plan was approved by the user beforehand, for the same plan and
   the same financial state, and each approval was used at most once.
4. Sandbox transaction idempotency keys are unique.

Usage:
    uv run python scripts/verify_evidence.py            # the committed evidence files
    uv run python scripts/verify_evidence.py FILE.json  # any exported log, including
                                                        # "Download audit log (JSON)" in the app
"""

import hashlib
import json
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "competition" / "evidence"
DEFAULT_LOGS = ("demo_15_steps.json", "sandbox_operation_log.json", "web_app_audit_log.json")
GENESIS_HASH = "0" * 64
USER_ONLY = {"PLAN_APPROVED", "PLAN_REJECTED", "SHOCK_CONFIRMED", "RESERVE_WITHDRAWN",
             "INCOME_CHANGE_CONFIRMED"}


def entry_hash(prev_hash: str, ts: str, actor: str, action: str, payload: dict) -> str:
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    material = "\n".join((prev_hash, ts, actor, action, payload_json))
    return hashlib.sha256(material.encode()).hexdigest()


def entries(log: dict) -> list[dict]:
    """Audit entries of a log exported by the scripts ("audit_log") or the web app ("entries")."""
    return log.get("audit_log") or log.get("entries") or []


def check_log(log: dict) -> list[str]:
    """Problems found in one exported log; an empty list means it passes."""
    problems: list[str] = []
    audit = entries(log)
    if not audit:
        return ["The log has no audit entries."]

    prev_hash = GENESIS_HASH
    for entry in audit:
        label = f"#{entry['seq']} {entry['action']}"
        if entry["prev_hash"] != prev_hash:
            problems.append(f"{label}: does not link to the entry before it.")
        expected = entry_hash(entry["prev_hash"], entry["ts"], entry["actor"],
                              entry["action"], entry["payload"])
        if entry["hash"] != expected:
            problems.append(f"{label}: hash does not match its content.")
        prev_hash = entry["hash"]

    approvals: dict[str, dict] = {}
    used: set[str] = set()
    for entry in audit:
        label = f"#{entry['seq']} {entry['action']}"
        payload = entry["payload"]
        if entry["action"] in USER_ONLY and entry["actor"] != "USER":
            problems.append(f"{label}: recorded by {entry['actor']}, but only the user may.")
        if entry["action"] == "PLAN_APPROVED":
            approvals[payload["approval_id"]] = payload
        if entry["action"] == "PLAN_EXECUTED":
            approval = approvals.get(payload["approval_id"])
            if approval is None:
                problems.append(f"{label}: no earlier approval by the user.")
            else:
                if approval["plan_id"] != payload["plan_id"]:
                    problems.append(f"{label}: executed a different plan than was approved.")
                if approval["state_hash"] != payload["state_hash_before"]:
                    problems.append(f"{label}: the finances changed after the approval.")
            if payload["approval_id"] in used:
                problems.append(f"{label}: approval {payload['approval_id']} used twice.")
            used.add(payload["approval_id"])

    keys = [t["idempotency_key"] for t in log.get("transactions", [])]
    if len(keys) != len(set(keys)):
        problems.append("Two sandbox transactions share an idempotency key.")
    return problems


def summary(log: dict) -> str:
    audit = entries(log)
    count = {action: sum(e["action"] == action for e in audit)
             for action in ("PLAN_APPROVED", "PLAN_EXECUTED")}
    refused = sum(e["action"].endswith(("REFUSED", "BLOCKED")) for e in audit)
    return (f"{len(audit)} audit entries, {count['PLAN_APPROVED']} approvals by the user, "
            f"{count['PLAN_EXECUTED']} executions, {refused} refused or blocked attempts, "
            f"{len(log.get('transactions', []))} sandbox transactions")


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv] or [EVIDENCE / name for name in DEFAULT_LOGS]
    failed = False
    for path in paths:
        log = json.loads(path.read_text(encoding="utf-8"))
        problems = check_log(log)
        if problems:
            failed = True
            print(f"FAIL {path.name}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"PASS {path.name}: {summary(log)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
