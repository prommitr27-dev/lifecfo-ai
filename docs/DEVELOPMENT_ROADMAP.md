# Development Roadmap

Submission deadline: **20 October 2026, 23:59 Beijing time (22:59 Bangkok)**.
Dates below are targets in Bangkok time. Every milestone ends with a runnable
app, passing tests, and a pushed commit, and adds its own minimal page.

Scoring weights from the competition rules shape the order: task completion
40%, security and compliance 30%, innovation and interaction 30%. The theme is
"AI as a Financial Participant", so the agent and its sandbox execution
evidence are core deliverables, not an add-on.

| # | Milestone | Exit criteria | Target | State |
|---|---|---|---|---|
| M0 | Repository and skeleton | `pytest` and the Streamlit app run in CI | 13 Oct | Done |
| M1 | Domain model and cash flow engine | Daily forecast matches hand-calculated values | 13 Oct | Done |
| M2 | Goal optimization, three strategies | Every plan passes the validator; identical plans are explained | 14 Oct | Done |
| M3 | Approval, sandbox, audit, tool permission tiers | Unapproved execution refused; duplicate execution creates nothing | 14 Oct | Done |
| M4 | ShockProof | Demo steps 4 to 5: a 20% income cut is detected as infeasible | 15 Oct | Done (15 Oct): demo steps 4 and 5 pass |
| M5 | Recovery engine | Demo steps 10 to 12: 10,000 THB emergency yields three recovery plans | 15 Oct | Done (15 Oct): demo steps 10 to 12 pass |
| M6 | Rewards engine | No duplicate XP; protected streak follows the rules; opt-out records nothing | 16 Oct | Done (15 Oct) |
| M7 | End-to-end deterministic demo | The 15-step demo runs from one script without an LLM; operation log exported | 16 Oct | Done (15 Oct) |
| M8 | AI CFO agent | Provider layer, read and compute tools, offline agent, and chat view are done (14 Oct). Remaining: propose and execute tools after M3, live test on a free provider, wider injection test set | 17 Oct | Partly done |
| M9 | Evaluation | 30 to 50 seeded scenarios; baseline comparison documented (`scripts/run_evaluation.py`, [results](testing/EVALUATION_RESULTS.md)) | 18 Oct | Done (15 Oct) |
| M10 | Submission package | Technical docs, deck, demo video, security self-assessment, execution evidence | 19 Oct | Done (19 Oct): all six items ready, see the [submission checklist](competition/SUBMISSION_CHECKLIST.md) |
| | Buffer and submit | Final check against the submission checklist | 20 Oct | |

## Scope adjustments after reading the rules

- Topic A names "bill analysis" and "spending insights". A small deterministic
  insights tool (upcoming bills, largest categories, share of income committed)
  is added to M7 and exposed to the agent in M8.
- The security self-assessment must describe the "permission-tier
  implementation", so the four tool tiers are built with the sandbox in M3
  rather than with the agent in M8.
- Execution evidence for non-on-chain topics is "simulated-account/sandbox
  operation logs and demo video", so M7 exports the audit log as a file.
- All submission material is in English, so the UI and documents are English.

## Work that does not depend on code

| Task | Owner | Needed by |
|---|---|---|
| Competitor analysis (Monarch, YNAB, Origin, Rocket Money, Cleo) with sources and dates | Member 3 | 18 Oct |
| Literature notes: multi-objective optimization, financial resilience, responsible gamification | Member 2, Member 3 | 18 Oct |
| Answers to the open questions in `FINANCIAL_MODEL.md` | Member 2 | 14 Oct |
| Shock definitions and draft risk thresholds | Member 3 | 15 Oct |
| Presentation deck (10 minutes maximum) | All | 19 Oct |
