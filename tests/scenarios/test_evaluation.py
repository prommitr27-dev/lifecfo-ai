"""M9 evaluation: reproducible, and LifeCFO's own plans never leave a cash gap."""

from lifecfo.evaluation import METHODS, evaluate, generate_scenarios, summarize
from lifecfo.evaluation.agent_eval import evaluate_agent


def test_scenarios_are_reproducible_from_the_seed():
    first, second = generate_scenarios(12), generate_scenarios(12)
    assert [s.after for s in first] == [s.after for s in second]
    assert evaluate(first) == evaluate(second)


def test_lifecfo_plans_never_go_negative_and_baselines_are_measured_alike():
    results = evaluate(generate_scenarios(12))
    assert {r.method for r in results} == set(METHODS)
    for r in results:
        if r.method == "LIFECFO" and r.outcome != "NO_PLAN_DISCLOSED":
            assert r.shortfall_days == 0 and not r.missed_essential_payment
    assert [row["scenarios"] for row in summarize(results)] == [12] * len(METHODS)


def test_agent_routes_every_prompt_and_resists_every_injection(demo_state):
    cases = evaluate_agent(demo_state)
    assert [c.prompt for c in cases if not c.passed] == []
