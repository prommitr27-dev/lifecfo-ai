"""The 15-step competition demo must keep passing end to end."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "demo_15_steps.py"


def test_every_demo_step_passes():
    spec = importlib.util.spec_from_file_location("demo_15_steps", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    steps, log = module.run()
    assert [s.number for s in steps] == list(range(1, 16))
    failed = [(s.number, name) for s in steps for name, ok in s.checks if not ok]
    assert failed == []
    assert log["audit_chain_intact"]
