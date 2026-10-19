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

## Try it

- **Live demo:** https://lifecfo-ai.streamlit.app/ (public, synthetic data,
  offline AI engine). Every visitor gets a private sandbox that disappears when
  the browser session ends. If the app is asleep, click the button to wake it.
- **Run it locally:** see [Quick start](#quick-start) below.
- **Test cases:** [docs/testing/TEST_CASES.md](docs/testing/TEST_CASES.md).

## Status

| Milestone | Scope | State |
|---|---|---|
| M0 | Repository, tooling, CI, documentation skeleton | Done |
| M1 | Domain model, envelope ledger, daily cash flow forecast, feasibility check | Done |
| M2 | Goal optimization, three validated planning strategies, plan validator | Done |
| AI layer | Provider-agnostic LLM access (Gemini free tier, Groq free plan, local Ollama, offline), agent tools with permission tiers, offline agent, chat view | Done (read and compute tools) |
| M3 | User approval, sandbox execution, idempotency, hash-chained audit log, Sandbox view | Done |
| Rules v0.2 | Financial Rules D1 to D9 (C1 to C10): position and deficits, buffer, reserve formula, debt interest and extra repayment, goal flexibility, acceptance tests AT1 to AT16 | Done except recording a real expense in the sandbox (see [status](docs/financial_model/RULES_V0.2_STATUS.md)) |
| M6 | Rewards: XP, levels, badges, daily and weekly streaks with grace, pause, and shock protection, adaptive recovery missions, opt-out, Rewards view; confirmed expenses and reserve withdrawals in the sandbox | Done |
| M7 | The brief's 15-step demo end to end with a check per step (`scripts/demo_15_steps.py`, all 15 pass) | Done |
| M9 | Evaluation: 40 seeded scenarios against three baselines, plus 20 routing and 10 injection prompts for the agent ([results](docs/testing/EVALUATION_RESULTS.md), regenerate with `uv run python scripts/run_evaluation.py`) | Done |
| M10 | Submission package: security self-assessment, licences, public demo, test cases, demo video | In progress |
| M6 to M10 | See [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Planned |

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). uv
uses Python 3.12 or newer if one is installed and downloads one otherwise.

```bash
git clone https://github.com/prommitr27-dev/lifecfo-ai.git
cd lifecfo-ai
uv sync
uv run pytest                      # 293 tests
uv run streamlit run app/main.py   # web app at http://localhost:8501
```

The app, the tests, and the demo run with **no API key, no paid service, and no
network**. An LLM is optional; see [docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md)
for the free options (local Ollama, Groq free plan, Gemini free tier).

Offline demo of the agent on synthetic data, and the 15-step competition demo
with a pass or fail check on every step:

```bash
uv run python scripts/demo_offline.py
uv run python scripts/demo_15_steps.py
```

Mobile app (iOS and Android, Expo) on top of an HTTP API over the same engines.
Needs Node.js 22; see [mobile/README.md](mobile/README.md). Run the API in one
terminal and the app in another:

```bash
uv run uvicorn lifecfo.api.main:app --host 0.0.0.0 --port 8000   # API docs at http://localhost:8000/docs
cd mobile && npm ci && npx expo start   # scan the QR code with Expo Go, or press w for a browser
```

## Deployment

| Where | How | Guide |
|---|---|---|
| Your machine | `uv sync`, then `uv run streamlit run app/main.py` | [Quick start](#quick-start) |
| Public web demo | Streamlit Community Cloud from `main`, secret `LIFECFO_SANDBOX = "session"` for a private sandbox per visitor | [docs/DEPLOY_STREAMLIT_CLOUD.md](docs/DEPLOY_STREAMLIT_CLOUD.md) |
| HTTP API and mobile app | `uv run uvicorn lifecfo.api.main:app`; set `LIFECFO_API_TOKEN` whenever others can reach it | [mobile/README.md](mobile/README.md) |
| Optional LLM | Set `LIFECFO_LLM_PROVIDER` and a free-tier key in `.env` or Cloud secrets; without one the offline engine answers | [docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md) |

Settings are read from environment variables (or Streamlit secrets):

| Variable | Default | Purpose |
|---|---|---|
| `LIFECFO_DB_PATH` | `.lifecfo/sandbox.db` | SQLite sandbox file for a local run |
| `LIFECFO_SANDBOX` | unset | `session` gives each browser session its own in-memory sandbox |
| `LIFECFO_LLM_PROVIDER` | `none` | `none`, `gemini`, `groq`, `ollama`, or `custom` |
| `LIFECFO_API_TOKEN` | unset | Bearer token required by every API endpoint except `/health` |

## Tests

```bash
uv run pytest                                  # unit, scenario, and integration tests
uv run ruff check .                            # lint
uv run python scripts/demo_15_steps.py         # the brief's 15-step flow, pass or fail per step
uv run python scripts/run_evaluation.py        # 40 scenarios vs baselines, routing and injection prompts
uv run python scripts/manual_scenarios.py      # hand-checkable scenario report
```

CI runs lint and the full suite on Python 3.12 and 3.14 for every push and pull
request, plus a type check and web build of the mobile app.

- [Test cases](docs/testing/TEST_CASES.md): 37 key cases with input, expected result, and the test that checks each
- [Testing plan](docs/testing/TESTING_PLAN.md): full inventory, evaluation method, and gaps
- [Evaluation results](docs/testing/EVALUATION_RESULTS.md) and [manual scenarios](docs/testing/MANUAL_SCENARIOS.md)

## Repository layout

```
app/                 Streamlit UI
mobile/              Expo mobile app (iOS, Android, web)
lifecfo/api/         HTTP API for the mobile app (FastAPI)
lifecfo/domain/      Shared models, money, clock, YAML loader
lifecfo/cashflow/    Daily forecast and feasibility check
lifecfo/optimization/  LP planner, three strategies, plan validator
lifecfo/llm/         Provider-agnostic LLM client and settings
lifecfo/agents/      Tool registry with permission tiers, offline and LLM agents
lifecfo/services/    Sandbox service: the only code path that changes state
lifecfo/database/    SQLite store and hash-chained audit log
lifecfo/debt/        Debt interest, payoff schedules, Avalanche and Snowball
lifecfo/rewards/     XP, missions, badges, and the streak state machine
scripts/             Demos, evaluation, and report generators
config/              Tunable assumptions owned by the modelling and risk leads
data/synthetic/      Synthetic profiles (money in baht, `_thb` suffix)
tests/               unit, integration, and expected-value scenario tests
docs/                Architecture, financial model, roadmap, competition checklist
```

## Documentation

- [System architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [Security design](docs/SECURITY_DESIGN.md)
- [Rewards system](docs/REWARDS_SYSTEM.md)
- [AI providers and zero-cost setup](docs/AI_PROVIDERS.md)
- [Public demo on Streamlit Community Cloud](docs/DEPLOY_STREAMLIT_CLOUD.md)
- [Financial model](docs/financial_model/FINANCIAL_MODEL.md) and [Rules v0.2 status](docs/financial_model/RULES_V0.2_STATUS.md)
- [Manual scenario validation](docs/testing/MANUAL_SCENARIOS.md)
- [Development roadmap](docs/DEVELOPMENT_ROADMAP.md)
- [Team tasks and interfaces](docs/TEAM_TASKS.md)
- [Security self-assessment](docs/competition/SECURITY_SELF_ASSESSMENT.md): permission tiers and known risks
- [Execution evidence](docs/competition/evidence/): 15-step demo report, sandbox operation log, chat transcript
- [Submission checklist](docs/competition/SUBMISSION_CHECKLIST.md)

## License

Released under the [MIT License](LICENSE). Licenses of all third-party Python
and npm packages are listed in
[docs/competition/THIRD_PARTY_LICENSES.md](docs/competition/THIRD_PARTY_LICENSES.md);
none conflicts with MIT.
