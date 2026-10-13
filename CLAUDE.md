# LifeCFO AI: instructions for Claude

## First thing in every session: ask who you are working with

Before doing any work in this repository, ask the person which team member
they are. Do this at the start of **every** session, even if a previous session
already asked, and do not guess from the git user name.

Ask exactly one short question, in Thai:

> คุณคือ Member คนไหนครับ: 1 (AI & Software), 2 (Financial Modeling) หรือ 3 (Risk & Evaluation)?

Then work within that member's area below. If a request falls in another
member's area, say whose area it is and ask whether to go ahead before changing
those files.

## Members

### Member 1: AI and Software Engineer (Joo, repository owner)

- Owns: architecture, all Python code (`lifecfo/`, `app/`), the agent, database,
  sandbox execution, tests, CI, and the GitHub workflow.
- May change anything. Pushes to `main` after tests pass.

### Member 2: Financial Modeling

- Owns: `docs/financial_model/FINANCIAL_MODEL.md`, `config/strategy_weights.yaml`,
  `tests/scenarios/expected/*.csv` (hand-calculated expected values), and later
  `docs/RECOVERY_ENGINE.md`.
- Typical work: decide and justify optimization weights and allocation rules,
  answer the open questions in the financial model, verify numbers the engine
  produces, add hand-calculated cases, analyse opportunity cost.
- Does not need to write Python. Help by explaining what the engine does in
  plain terms, running the app and tests, and editing YAML, CSV, and Markdown.
  Do not change code in `lifecfo/` for Member 2; write the requested change as a
  note for Member 1 instead (a GitHub issue or a section in `docs/TEAM_TASKS.md`).

### Member 3: Risk and Evaluation

- Owns: `config/risk_thresholds.yaml`, `data/synthetic/*.yaml`,
  `data/scenarios/*.yaml`, and the documents `SHOCKPROOF_DESIGN.md`,
  `TESTING_PLAN.md`, `COMPETITOR_ANALYSIS.md`, and the security self-assessment.
- Typical work: define shock types and risk thresholds, build synthetic
  profiles and scenarios with expected outcomes, define evaluation metrics and
  baselines, write security and prompt-injection test cases, research
  competitors with sources and dates.
- Does not need to write Python. Same rule as Member 2 for code in `lifecfo/`.

Full deliverables per milestone are in `docs/TEAM_TASKS.md`. Step-by-step guides
in Thai for Members 2 and 3 are in `docs/team/`; point them there, and prefer
the templates in `docs/team/templates/` over inventing new file formats.

## Working rules for everyone

- Talk to the team in Thai. Write code, documentation, commit messages, and
  GitHub issues in English.
- Submission deadline: 20 October 2026, 23:59 Beijing time (22:59 Bangkok). See
  `docs/DEVELOPMENT_ROADMAP.md` for the current milestone.
- Synthetic data only. Never commit `.env`, API keys, or real financial data.
- Money is integer satang in code; profiles write baht with a `_thb` suffix.
- The LLM never calculates money. Every allocation must pass
  `lifecfo.optimization.validate_plan`.
- Before committing: `uv run ruff check .` and `uv run pytest` must pass.
- Do not force-push, delete branches, or rewrite history. Pull before pushing.
- Label draft numbers as assumptions. Do not report results the repository
  cannot regenerate, and do not invent citations.

## Commands

```bash
uv sync
uv run pytest
uv run ruff check .
uv run streamlit run app/main.py
```
