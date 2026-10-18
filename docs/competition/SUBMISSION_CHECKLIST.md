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
| 1 | Technical documentation | System architecture, core algorithm description, security design | `docs/architecture`, `docs/financial_model`, `docs/SECURITY_DESIGN.md` | Architecture, financial model, and security design written for M0 to M3 |
| 2 | Presentation deck | Final presentation of at most 10 minutes | `docs/competition/` | Not started |
| 3 | Demo video | Optional, at most 5 minutes | Link in README | Not started |
| 4 | Source code | README, GitHub repository link, deployment instructions, test cases | This repository | In progress; evaluation against baselines in `docs/testing/EVALUATION_RESULTS.md` |
| 5 | Security self-assessment report | Permission-tier implementation and known-risk list | `docs/competition/SECURITY_SELF_ASSESSMENT.md` | Draft written; for Member 3 to review |
| 6 | Execution evidence | Simulated-account or sandbox operation logs and demo video | `docs/competition/evidence/` | 15-step demo report and log (`scripts/demo_15_steps.py`), chat transcript and sandbox operation log (`scripts/demo_offline.py`); demo video not started |

## Before submitting

- [ ] Team registered on the official site.
- [ ] Repository visible to reviewers (it is private during development).
- [ ] A licence file is chosen and dependencies' licences are listed.
- [ ] README quick start works on a clean machine.
- [ ] Every number in the deck can be regenerated from the repository.
