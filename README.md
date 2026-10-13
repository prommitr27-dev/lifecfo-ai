# LifeCFO AI

**Your financial plan should adapt when life doesn't.**

LifeCFO AI is an agentic personal finance assistant built for FinTechathon 2026
(International Track, Topic A: Personal Finance Assistant). It combines four
capabilities on one shared financial state:

1. **Personal CFO**: multi-goal planning with three validated strategies.
2. **ShockProof**: stress testing and risk indicators for income and expense shocks.
3. **Financial Recovery**: adaptive replanning after a confirmed emergency.
4. **Goal Rewards & Streak**: responsible gamification that adapts during hardship.

Every number comes from deterministic Python engines. The AI agent understands
requests, calls tools, and explains results; it never computes money on its own
and cannot approve or execute a plan without the user.

All data is synthetic and all execution happens in a sandbox ledger. No real
accounts, credentials, or transactions are involved. This project does not give
investment advice.

## Status

| Milestone | Scope | State |
|---|---|---|
| M0 | Repository, tooling, CI, documentation skeleton | Done |
| M1 | Domain model, envelope ledger, daily cash flow forecast, feasibility check | Done |
| M2 | Goal optimization, three validated planning strategies, plan validator | Done |
| M3 | Approval, sandbox execution, audit log, tool permission tiers | Next |
| M4 to M10 | See [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Planned |

## Quick start

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run streamlit run app/main.py
```

The app and the test suite run in deterministic mock mode by default and need
no API key. See `.env.example` for the optional LLM settings.

## Repository layout

```
app/                 Streamlit UI
lifecfo/domain/      Shared models, money, clock, YAML loader
lifecfo/cashflow/    Daily forecast and feasibility check
lifecfo/optimization/  LP planner, three strategies, plan validator
config/              Tunable assumptions owned by the modelling and risk leads
data/synthetic/      Synthetic profiles (money in baht, `_thb` suffix)
tests/               unit, integration, and expected-value scenario tests
docs/                Architecture, financial model, roadmap, competition checklist
```

## Documentation

- [System architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [Financial model](docs/financial_model/FINANCIAL_MODEL.md)
- [Development roadmap](docs/DEVELOPMENT_ROADMAP.md)
- [Team tasks and interfaces](docs/TEAM_TASKS.md)
- [Submission checklist](docs/competition/SUBMISSION_CHECKLIST.md)
