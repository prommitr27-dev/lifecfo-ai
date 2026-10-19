# Submission Checklist

Source: "PBCSF Appendix 2: Problem Description and Competition Rules for
International Track" (PDF provided by the team, read 2026-10-13). Page 1 of the
PDF is an image with no extractable text and was not reviewed. Full terms are
on the official site, fintechathon.g-ican.com, and should be checked before
submitting.

## Key facts

- Track theme: "AI as a Financial Participant". Each team builds an AI agent
  capable of completing real tasks in a financial scenario.
- Our topic: **A, Personal Finance Assistant** (smart budgeting, bill analysis,
  spending insights, actionable recommendations from income and expenses).
- Deadline for registration and submission: **20 October 2026, 23:59 Beijing
  time (UTC+8)**, which is 22:59 in Bangkok. Submissions can be updated until
  then; the latest version counts.
- Language: English for submissions, presentations, and review.
- Scoring: task completion 40%, security and compliance 30%, innovation and
  interaction 30%. The 0 to 5 point bonus applies to the on-chain topic only.
- Teams of 2 to 5 full-time students at institutions outside Mainland China,
  Hong Kong, Macao, and Chinese Taipei; at least 60% non-Chinese nationals.
- Third-party data, code, and open-source components must be properly licensed.
- Finalists are announced on 31 October; the final is in Shenzhen, 21 to 23
  November, and at least one member must attend in person.

## Deliverables

| # | Item | Requirement | Where it will live | State |
|---|---|---|---|---|
| 1 | Technical documentation | System architecture, core algorithm description, security design | `docs/architecture`, `docs/financial_model`, `docs/SECURITY_DESIGN.md`, `docs/SHOCKPROOF_DESIGN.md`, `docs/RECOVERY_ENGINE.md` | Architecture, financial model, and security design written for M0 to M3; ShockProof and recovery design drafted for Members 3 and 2 to review |
| 2 | Presentation deck | Final presentation of at most 10 minutes | `docs/competition/` | Not started |
| 3 | Demo video | Optional, at most 5 minutes | Link in README | Recorded on 19 October 2026 on the current app (4:49, all 15 steps of `docs/competition/evidence/demo_15_steps.md`, English captions); to be uploaded and linked |
| 4 | Source code | README, GitHub repository link, deployment instructions, test cases | This repository | README with live demo link, deployment table and settings; key test cases with inputs and expected results in `docs/testing/TEST_CASES.md`; evaluation against baselines in `docs/testing/EVALUATION_RESULTS.md`; test plan drafted in `docs/testing/TESTING_PLAN.md` and competitor analysis in `docs/COMPETITOR_ANALYSIS.md`, both for Member 3 to review |
| 5 | Security self-assessment report | Permission-tier implementation and known-risk list | `docs/competition/SECURITY_SELF_ASSESSMENT.md` | Updated 19 October 2026 for the public demo, with focus areas (financial data, user access, wrong advice) and 14 known risks; for Member 3 to review |
| 6 | Execution evidence | Simulated-account or sandbox operation logs and demo video | `docs/competition/evidence/` | 15-step demo report and log (`scripts/demo_15_steps.py`), chat transcript and sandbox operation log (`scripts/demo_offline.py`); demo video not started |

## Before submitting

- [ ] Team registered on the official site.
- [x] Repository visible to reviewers (public since 18 October 2026).
- [x] A licence file is chosen ([MIT](../../LICENSE)) and dependencies' licences are listed ([THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)).
- [x] README quick start works on a clean machine (checked 18 October 2026 on a fresh clone with empty uv and npm caches: tests, demos, web app, API, and mobile web app).
- [ ] Every number in the deck can be regenerated from the repository.
