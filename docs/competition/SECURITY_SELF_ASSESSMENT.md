# Security Self-Assessment

Project: LifeCFO AI (FinTechathon 2026, International Track, Topic A).
Assessed version: `main` on 19 October 2026, including the public web demo at
https://lifecfo-ai.streamlit.app/. Assessed by the team; this is a
self-assessment, not an external audit.

Detailed design, with the test for every control, is in
[`docs/SECURITY_DESIGN.md`](../SECURITY_DESIGN.md). This report summarises it
for reviewers and adds the HTTP API used by the mobile app and the public web
demo.

## 1. Summary

- The AI agent is a **participant with limited rights**, not an operator. It
  can read, compute, and propose. It can never approve, and it can execute only
  a plan the user has already approved.
- Every figure comes from deterministic Python engines. The language model, if
  one is enabled, only routes requests and writes explanations, and any number
  it states that no tool produced causes its answer to be discarded.
- All money movement happens in a **sandbox ledger** on synthetic data. There
  is no bank connection, no credential handling, and no real transaction
  anywhere in the code.
- Each control below is enforced in code and demonstrated by an automated test.
  The full suite (298 tests) runs in CI on Python 3.12 and 3.14 with no LLM and
  no network.

## 2. Permission-tier implementation

Every agent tool is registered with a tier in `lifecfo/agents/tools.py`. An
agent is built with a maximum tier, and the registry refuses any call above it
before the tool runs. Tier checks do not depend on anything the model says.

| Tier | What it allows | Tools | Changes stored state |
|---|---|---|---|
| 0 READ | Look at the profile, goals, spending, audit log, rewards | 5 tools | No |
| 1 COMPUTE | Forecasts, feasibility, risk indicators, plan optimisation, debt comparison, what-if simulations | 8 tools | No; runs on copies of frozen models |
| 2 PROPOSE | Store a validated plan as a proposal waiting for the user | `request_plan_approval` | A proposal row only; money and the active plan are untouched |
| 3 EXECUTE | Apply a plan the user approved | `execute_approved_sandbox_plan` | Yes, only with a valid, unused user approval |

There is **no approve tool at any tier**. Approval is created only by
`SandboxService.decide`, which refuses every actor except `USER` and is called
only from the Approve and Reject buttons (Streamlit) or the decision endpoint
the mobile app calls when the user taps them.

The path from a request to a change in the sandbox:

1. The agent (or the user) asks for a plan. The optimiser builds it and
   `validate_plan` checks it.
2. `request_plan_approval` stores it as a proposal. Nothing else changes.
3. The user approves. The approval records the plan's hash and the state's hash.
4. On execution the service re-validates the plan, recomputes both hashes, and
   refuses if either differs or the approval was already used. The transaction
   carries a unique idempotency key, so a repeated call creates nothing.
5. Every step, including every refusal, is appended to a hash-chained audit log.

## 3. Controls and evidence

| # | Risk addressed | Control | Evidence (test) |
|---|---|---|---|
| S1 | Agent acts without consent | Execution requires an approval that only the user can create | `test_execution_without_any_approval_is_refused`, `test_agent_cannot_approve` |
| S2 | Approved plan swapped or state changed after approval | Approval bound to plan hash and state hash | `test_tampered_stored_plan_is_not_executed`, `test_approval_is_void_when_the_state_changes` |
| S3 | Double execution | Single-use approval and `UNIQUE` idempotency key | `test_duplicate_execution_changes_nothing` |
| S4 | Invalid or unsafe allocation | `validate_plan` on generation, proposal, and execution | `test_validator_rejects_tampered_and_stale_plans` |
| S6 | Simulation leaks into real data | Pure engines over frozen models | `test_tools_never_change_the_state` |
| S7 | Hidden changes to history | Append-only audit log, each entry hashes the previous | `test_audit_chain_detects_tampering`, `test_audit_chain_detects_a_deleted_entry` |
| S8 | Model invents figures | Numbers in an answer must appear in a tool result | `test_invented_figures_are_replaced_by_the_verified_explanation` |
| S9 | Prompt injection raises privileges | Tier and approval checks ignore model output; user text is data, capped at 2,000 characters | `test_prompt_injection_cannot_reach_a_higher_tier` |
| S10 | Malformed input | Bounded Pydantic models on every tool, domain object, and API body | `test_unknown_tools_and_bad_arguments_are_refused_as_data` |
| S11 | Provider outage causes unsafe behaviour | Any provider error falls back to the offline engine; never a paid service | `test_every_provider_failure_falls_back_to_offline_mode` |
| S12 | Secret leakage | `.env` and databases git-ignored; keys never appear in error text | `test_error_text_never_contains_the_api_key` |
| S13 | A plan is offered when none is safe | Planner reports the shortfall and offers no plan | `test_no_plan_is_invented_when_essentials_cannot_be_paid` |
| S15 | Agent records events in the user's name | Expenses, income changes, and reserve withdrawals accept only `USER` and void earlier approvals | `test_only_the_user_can_confirm_an_expense_or_withdraw` |
| S16 | Reward farming | No tool writes rewards; reward event ids are unique per item and period | `test_goal_milestones_pay_once_from_the_stored_state` |
| A1 | Mobile client sends its own plan | The API never accepts a plan from the client; it regenerates it from stored state | `test_client_cannot_send_its_own_plan_or_approve_without_a_proposal` |
| A2 | Chat via API approves | The API chat agent runs as `AGENT` | `test_chat_agent_cannot_approve` |
| A3 | Unauthenticated API access | If `LIFECFO_API_TOKEN` is set, every endpoint except `/health` needs the bearer token, compared in constant time | `test_token_is_required_when_configured` |
| W1 | One visitor of the public demo sees or changes another's data | With `LIFECFO_SANDBOX = "session"` each browser session gets its own in-memory sandbox; nothing is written to disk and it is gone when the session ends | `test_public_mode_gives_each_visitor_a_private_sandbox` |
| W2 | Moving the what-if slider changes data | The slider previews on a copy; only "Save as my real income" records a change, through the same user-only path as S15 | `test_moving_the_what_if_slider_leaves_the_page_alone`, `test_saving_the_what_if_records_a_real_income_change` |

The full list (S1 to S16) is in `docs/SECURITY_DESIGN.md`, section 3.

## 4. Adversarial evaluation

`scripts/run_evaluation.py` runs 10 prompt-injection attempts against the
offline agent, in English and Thai, including fake system messages, claimed
prior approval, "developer mode", and direct transfer requests. Results in
[`docs/testing/EVALUATION_RESULTS.md`](../testing/EVALUATION_RESULTS.md):

- **10 of 10** left the plan unapproved, recorded no transaction, and changed
  no balance. In three cases the agent did call the execute tool, and the tool
  refused because no user approval existed. This is the intended design: safety
  does not depend on the agent choosing correctly.
- 20 of 20 routing prompts reached the expected tool, with every number in the
  answer traced to a tool result.

LLM providers are not part of this regenerable run, because free tiers change
and rate-limit. Their safety layers are covered by unit tests with a scripted
model, and live checks on GroqCloud and Gemini are recorded in
`docs/AI_PROVIDERS.md`.

## 5. Focus areas

How the system handles the three areas the brief asks teams to consider.

**Protecting financial data.**
- Only synthetic profiles exist anywhere in the system; there is no bank
  connection, no account number, and no credential to protect.
- Money moves only inside the sandbox ledger, through `SandboxService`, the one
  code path that changes state (S1 to S4, S15).
- History is append-only and hash-chained, so a changed or deleted entry is
  detected (S7). It is tamper-evident, not tamper-proof (R3).
- API keys live in `.env` or Streamlit secrets, never in the repository, and
  never appear in error text (S12). The public repository's history was scanned
  for secrets before it was made public on 18 October 2026.

**Access to user data.**
- The AI agent sees data only through tools, each with a tier (section 2). It
  can read and compute, propose at most, and never approve.
- The public demo isolates every visitor in a private, temporary sandbox (W1).
  There is no sign-in, so a visitor is "the user" of their own sandbox only (R2).
- The API used by the mobile app needs a bearer token whenever one is set (A3);
  without it, anyone on the network can act (R9).
- With an LLM enabled, the question and tool results go to the chosen provider
  (section 6). The public demo runs with no LLM, so nothing leaves the server.

**Risk of wrong advice.**
- Every number comes from deterministic engines, and an answer with a figure no
  tool produced is discarded (S8).
- Every plan passes `validate_plan` and a daily cash check before the user sees
  it, and again before execution (S4). When no safe plan exists, none is offered
  (S13).
- Nothing changes until the user approves; the agent cannot approve (S1).
- Assumptions are shown with each result (month-end savings sweep, essentials as
  monthly lump sums, draft strategy weights). Residual risks are R1, R4 and R12.
- The system plans cash flow, reserves, debt and goals only; it gives no
  investment advice.

## 6. Data handling and compliance

- Synthetic profiles only, in development, tests, demos, and evaluation.
- Default mode is offline: nothing leaves the machine.
- With an LLM enabled, the question, recent chat, tool definitions, and tool
  results (figures from the synthetic profile) are sent to the chosen provider.
  Provider privacy notes are in `docs/AI_PROVIDERS.md`.
- No investment advice: the system plans cash flow, reserves, debt, and goals;
  it does not recommend securities.
- Responsible gamification: rewards are opt-in, opt-out records nothing, and
  streaks are protected rather than broken during a confirmed shock.

## 7. Known risks

| # | Risk | Severity in the MVP | Status and mitigation |
|---|---|---|---|
| R1 | The number check catches invented figures, not wrong statements with correct figures | Medium | Observed once in live testing; a prompt rule reduces it. Offline mode is unaffected |
| R2 | No sign-in in the web app; anyone who opens it acts as the user | Medium | On the public demo each visitor only reaches a private, temporary sandbox (W1). A deployment with real users needs authentication before Approve means anything |
| R3 | Audit log is tamper-evident, not tamper-proof; someone with write access to the database could rebuild the chain | Low | Accepted. Anchoring the latest hash externally would close it |
| R4 | Offline router matches keywords and can pick the wrong read-only tool | Low | It cannot exceed its tier, and execution still needs approval |
| R5 | Free LLM tiers may log or train on prompts | Low | Only synthetic data is sent; documented per provider |
| R6 | Sandbox database not encrypted at rest | Low | Synthetic data only |
| R7 | The approving actor is a label, not a verified identity | Medium | Follows from R2 and R9 |
| R8 | The daily check-in proves intent, not that the user reviewed anything | Low | Pays at most 10 XP a day |
| R9 | The API token is optional; without it any client on the network can approve and execute in the sandbox | Medium | `mobile/README.md` says to set `LIFECFO_API_TOKEN` whenever the API is reachable by others. Required for any shared deployment |
| R10 | The API allows any CORS origin | Low | Needed for Expo web and LAN devices; the token is the guard when set |
| R11 | No rate limiting on the API or chat | Low | Single-user demo server; a deployment would add it |
| R12 | A plan can be valid yet unsuitable because the model's assumptions are wrong for the person (draft strategy weights, risk thresholds not yet set, savings swept at month end, bills as monthly lump sums) | Medium | Assumptions are labelled in every result; the user compares three plans and must approve one; risk indicators are shown without ratings until thresholds are set |
| R13 | The public demo can be overloaded; Streamlit Community Cloud gives limited resources and no rate limit | Low | Synthetic data only; an overloaded app restarts with a fresh sandbox |
| R14 | If an LLM key is added to the public demo's secrets, anyone with the link can spend its quota | Low | The public demo runs without a key. `docs/DEPLOY_STREAMLIT_CLOUD.md` warns about this and recommends a free-tier key with a limit |

## 8. How to reproduce

```bash
uv sync
uv run pytest                              # all controls above
uv run pytest -k "sandbox or agent or api"  # the permission and approval controls only
uv run python scripts/run_evaluation.py    # injection and routing results
uv run python scripts/demo_15_steps.py     # sandbox operation log with audit chain
```
