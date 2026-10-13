# Security Design

Scope: the MVP as implemented. Each control lists the test that demonstrates it.
Everything runs on synthetic data in a local sandbox; there are no real
accounts, credentials, or transactions anywhere in the system.

## 1. Trust boundaries

```
User (browser)  -->  Streamlit app  -->  SandboxService  -->  SQLite sandbox
                          |                    ^
                          v                    |  tools only, tier-limited
                     Agent (offline router or LLM)
                          |
                          v
                Optional LLM provider (external or local)
```

- The **user** is the only party that can approve a plan.
- The **agent** is untrusted with respect to state: whatever it outputs is
  treated as a request that the tool registry and the service may refuse.
- An **LLM provider**, when enabled, is untrusted. Its text is checked and its
  tool calls are validated. Nothing depends on the provider behaving well.

## 2. Permission tiers

Implemented in `lifecfo/agents/tools.py`. Every tool has a tier; an agent is
created with a maximum tier and the registry refuses anything above it.

| Tier | Tools | Can change stored state |
|---|---|---|
| 0 READ | `get_financial_profile`, `get_financial_goals`, `get_spending_insights`, `get_audit_history` | No |
| 1 COMPUTE | `get_cash_flow_forecast`, `optimize_financial_plan`, `simulate_income_change`, `simulate_unexpected_expense` | No. Runs on copies |
| 2 PROPOSE | `request_plan_approval` | Stores a proposal only. Money and plan are untouched |
| 3 EXECUTE | `execute_approved_sandbox_plan` | Yes, but only with a valid, unused approval from the user |

There is **no tool for approving**. `SandboxService.decide` is called only by
the Approve and Reject buttons in the app, and it refuses any actor other than
`USER`.

## 3. Controls

| # | Control | How it is enforced | Test |
|---|---|---|---|
| S1 | Human approval before any state change | `execute` requires an approval row created by `decide`, which only accepts the user | `test_execution_without_any_approval_is_refused`, `test_agent_cannot_approve`, `test_llm_cannot_execute_without_approval_even_at_execute_tier` |
| S2 | Approval is bound to what was approved | Approval stores the plan hash and state hash; execution recomputes both | `test_tampered_stored_plan_is_not_executed`, `test_approval_is_void_when_the_state_changes` |
| S3 | No duplicate execution | Approval is single use, and the transaction's idempotency key is `UNIQUE` in SQLite | `test_duplicate_execution_changes_nothing` |
| S4 | Deterministic validation of every plan | `validate_plan` runs when a plan is generated, proposed, and again before execution | `test_validator_rejects_tampered_and_stale_plans`, `test_invalid_plan_is_not_stored` |
| S5 | Unapproved plans are read-only | Proposing and approving do not alter state | `test_happy_path_propose_approve_execute` |
| S6 | Simulations never alter stored data | Engines are pure functions over frozen models | `test_forecast_does_not_mutate_state`, `test_tools_never_change_the_state` |
| S7 | Tamper-evident audit log | Append-only, each entry hashes the previous one; refusals and failures are logged too | `test_audit_chain_detects_tampering`, `test_audit_chain_detects_a_deleted_entry` |
| S8 | The LLM cannot invent figures | Every number of 100 or more in an answer must appear in a tool result, otherwise the answer is replaced by the deterministic explanation | `test_invented_figures_are_replaced_by_the_verified_explanation` |
| S9 | Prompt injection cannot raise privileges | Tool tier and approval checks do not depend on model output; user text is passed as data and truncated to 2,000 characters | `test_prompt_injection_cannot_reach_a_higher_tier`, `test_no_tool_lets_the_agent_approve` |
| S10 | Invalid input is rejected | Pydantic models with bounds on every tool input and domain object | `test_unknown_tools_and_bad_arguments_are_refused_as_data`, `test_negative_and_zero_amounts_rejected` |
| S11 | Provider failure is safe | Any provider error ends in the offline engine; no automatic provider switch, never a paid service | `test_every_provider_failure_falls_back_to_offline_mode` |
| S12 | Secrets stay local | `.env` and the sandbox database are git-ignored; error messages never contain keys | `test_error_text_never_contains_the_api_key` |
| S13 | No plan is invented | When essentials cannot be paid the planner returns no plan and reports the shortfall | `test_no_plan_is_invented_when_essentials_cannot_be_paid` |
| S14 | Sandbox only | No code path opens a bank connection or handles credentials; "execution" updates the sandbox ledger | By construction |

## 4. Data handling

- Development, tests, and demos use synthetic profiles only.
- In the default offline mode nothing leaves the machine.
- With an LLM provider enabled, a chat question sends the system rules, the
  user's message, recent chat history, tool definitions, and the tool results
  (which contain figures from the profile) to that provider. See
  `docs/AI_PROVIDERS.md` for each provider's privacy notes.

## 5. Known risks and limitations

| # | Risk | Status |
|---|---|---|
| R1 | The number check catches invented figures, not invented statements. A model can describe something qualitatively wrong with correct numbers | Observed once in live testing. Mitigated by a prompt rule; not eliminated. Offline mode is unaffected |
| R2 | The app is single-user with no authentication. Anyone who can open it acts as the user | Accepted for the MVP. A deployed version needs sign-in before the Approve button means anything |
| R3 | The audit log is tamper-evident, not tamper-proof. Someone with write access to the database file could rebuild the whole chain | Accepted for the MVP. An external anchor for the latest hash would close this |
| R4 | The offline router matches keywords, so an unusual phrasing can route to the wrong read-only tool | Low impact: it can only reach tools within its tier, and execution still needs approval |
| R5 | Free LLM tiers may log or train on prompts | Only synthetic data is sent; documented per provider |
| R6 | The sandbox database is not encrypted at rest | Accepted: it holds synthetic data only |
| R7 | Approval records the actor as a label passed by the caller, not a verified identity | Follows from R2 |
| R8 | Reserve drawdown, recovery planning, and rewards are not implemented yet, so their controls are not covered here | Planned (M4 to M6) |
