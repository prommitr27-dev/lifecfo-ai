# Competitor Analysis

Owner: Member 3 (Risk and Evaluation).

> **Status: DRAFT for review by Member 3.** Drafted on 18 October 2026 for the
> submission package. Every competitor claim links to a source opened on
> **18 October 2026**, from the vendor's own site or help centre wherever
> possible. Where a source did not confirm something it is marked
> **Unverified** rather than guessed. "Unverified" for a feature means it was
> not found, not that it is proven absent. The LifeCFO column describes the
> code on `main` (commit `a0c4fa8`).

## 1. Feature comparison

Yes, No, Partial, or Unverified. Details and sources are in section 2.

| Capability | LifeCFO AI | Monarch Money | YNAB | Origin | Rocket Money | Cleo | MAKE by KBank |
|---|---|---|---|---|---|---|---|
| Expense tracking and budgeting | Partial (scheduled budgets and bill insights; no transaction import) | Yes | Yes | Yes | Yes | Yes | Yes |
| Multiple goals with priorities and deadlines | Yes | Yes | Yes | Unverified | Partial | Partial | Partial |
| Optimized allocation across competing goals | Yes (linear program) | No | Partial (fixed rule order) | No ("coming soon") | Partial (balance-based transfers) | Partial | No |
| What-if or stress testing of the plan | Yes | Yes (Plus tier) | Partial | Yes (Monte Carlo) | Unverified | Partial | Unverified |
| Automatic replanning after an emergency | Yes, once the user confirms the event | Unverified | No | No | Partial | Yes (waitlist) | Unverified |
| Conversational AI assistant | Yes | Yes | No (native) | Yes | Yes | Yes | No |
| AI takes actions with user approval | Yes (sandbox only) | No evidence | No | Partial | Yes | Yes | No |
| Explanation of trade-offs between plans | Yes | Partial | Unverified | Partial | Unverified | Partial | Unverified |
| Streaks or gamification | Yes | Unverified | Unverified | Unverified | Unverified | Partial | Yes |
| Streak adapts during financial hardship | Yes | Unverified | Unverified | Unverified | Unverified | Unverified | Unverified |
| Bank account linking | No | Yes (US, CA) | Yes (US, CA, UK, EU) | Yes (US) | Yes (US) | Partial | Own KBank account |
| Usable in Thailand | Yes (THB, Thai prompts; synthetic data) | No | Partial (no Thai bank linking) | No | No | No | Yes |

## 2. Per competitor

### Monarch Money

- **What it does.** A paid, US-focused app for budgeting, net worth and goals,
  with an AI Assistant, Insights and a Weekly Recap. The Plus tier adds
  forecasting with life events and saved scenarios compared side by side.
- **Similar to LifeCFO in.** Several goals with target dates; scenario
  comparison; conversational assistant.
- **Leaves open.** Money is allocated to goals by hand or by rule, not by an
  optimizer. The assistant explains and guides; no source documents it acting.
  Scenarios show differences per metric without a written trade-off. No
  emergency event or automatic replanning was found. Only USD and CAD accounts.
- **How LifeCFO differs.** Allocation across the reserve and competing goals
  is optimized under a daily liquidity constraint, and plans come with
  explanations derived from the numbers.
- **Sources (opened 18 Oct 2026).**
  [Getting started](https://help.monarch.com/hc/en-us/articles/360048393272-Getting-Started-with-Monarch),
  [Goals 3.0](https://help.monarch.com/hc/en-us/articles/44373110771860-Introducing-Goals-3-0),
  [Forecasting](https://help.monarch.com/hc/en-us/articles/48344305092244-Forecasting-in-Monarch),
  [AI in Monarch](https://help.monarch.com/hc/en-us/articles/37526856682260-AI-in-Monarch),
  [AI features](https://help.monarch.com/hc/en-us/articles/16116906962452-About-Monarch-s-AI-Features),
  [International accounts](https://help.monarch.com/hc/en-us/articles/360048393552-International-Accounts-and-Currency),
  [Pricing](https://www.monarch.com/pricing) (Core 14.99 USD a month or 99.99 USD a year; Plus price not shown).

### YNAB (You Need A Budget)

- **What it does.** Zero-based budgeting ("give every dollar a job") with
  targets. The "Underfunded" auto-assign fills categories in a fixed order
  (overspent, then by due date, then end of month, then future targets, then
  credit cards). There is no native AI assistant; its ChatGPT app only
  surfaces help content.
- **Similar to LifeCFO in.** Targets with due dates and a priority order.
- **Leaves open.** The allocation is a fixed rule, not an optimization, and
  stops when money runs out. For tight months the advice is to adjust targets
  by hand. No scenario engine; Thai banks cannot be linked.
- **How LifeCFO differs.** It replans after a confirmed shock, checks every
  day's cash, and offers three strategies with their trade-offs.
- **Sources (opened 18 Oct 2026).**
  [Underfunded guide](https://support.ynab.com/en_us/underfunded-a-guide-BJwPhQO09.md),
  [Edit Plan](https://support.ynab.com/plan-and-adjust-with-edit-plan-and-cost-to-be-me-ByR7vpqPyx),
  [Budgeting when broke](https://www.ynab.com/blog/how-to-budget-in-ynab-when-youre-broke),
  [YNAB and ChatGPT](https://support.ynab.com/en_us/ynab-and-chatgpt-H1QI25JRZe.md),
  [Snooze a target](https://support.ynab.com/snooze-a-target-HyS4E5rZT),
  [Pricing](https://www.ynab.com/pricing) (14.99 USD a month or 109 USD a year).

### Origin

- **What it does.** An all-in-one US app: budgeting, investing, Monte Carlo
  forecasting, tax filing and estate planning. A multi-agent "AI Advisor" is
  backed by an SEC-registered investment-adviser subsidiary, and human
  planners are available.
- **Similar to LifeCFO in.** Conversational advisor; what-if forecasting with
  life events; the AI can build or update budgets.
- **Leaves open.** Custom savings prioritisation is listed as "coming soon".
  Replanning after an emergency is not described. Moving money and an
  approval step for AI actions are not documented. US accounts only.
- **How LifeCFO differs.** Goal prioritisation is already optimized, and any
  money movement is a separate, user-approved, audited sandbox step.
- **Sources (opened 18 Oct 2026).**
  [Spending](https://useorigin.com/products/spending),
  [Financial planning](https://support.useorigin.com/hc/en-us/articles/9313399292429-How-does-Origin-s-Financial-Planning-feature-work),
  [Forecasting guide](https://support.useorigin.com/hc/en-us/articles/40506069128845-A-Guide-to-Our-Forecasting-Tool),
  [AI Advisor](https://support.useorigin.com/hc/en-us/articles/39419419459085-What-is-the-AI-Advisor),
  [International accounts](https://support.useorigin.com/hc/en-us/articles/33490171963149-Does-Origin-support-international-account-connection),
  [Vendor blog, pricing](https://useorigin.com/resources/blog/how-does-origins-ai-advisor-compare-to-monarch-and-other-ai-finance-apps) (1 USD the first year, then 99 USD a year).

### Rocket Money

- **What it does.** A US app for subscriptions, bills, budgeting and automated
  savings, with concierge bill negotiation and cancellation. Its texting
  agent "Rowan" (Premium+) can start cancellations and negotiations, build
  budgets and recategorise transactions.
- **Similar to LifeCFO in.** An AI agent that takes actions; savings that
  adapt to the account balance ("balance protection").
- **Leaves open.** The product page says "anything that touches your money
  waits for your go-ahead", while the help centre says Rowan "may ask you to
  confirm" certain actions, so the approval rule is not stated precisely.
  Savings transfers follow the checking balance, not an optimization across
  goals. No forecasting was found. US banks only.
- **How LifeCFO differs.** The approval rule is enforced in code: the agent
  has no approve tool, an approval is bound to the plan and state hashes, and
  it is single use (security controls S1 to S3).
- **Sources (opened 18 Oct 2026).**
  [Cost](https://help.rocketmoney.com/en/articles/2217739-how-much-does-rocket-money-cost),
  [Financial goals](https://help.rocketmoney.com/en/articles/2620940-financial-goals-overview),
  [Pricing and Smart Savings](https://www.rocketmoney.com/learn/personal-finance/how-much-does-rocket-money-cost),
  [What is Rowan](https://help.rocketmoney.com/en/articles/16760933-what-is-rowan),
  [Rowan product page](https://www.rocketmoney.com/rowan),
  [International banks](https://help.rocketmoney.com/en/articles/79778-does-rocket-money-support-international-banks).

### Cleo

- **What it does.** A chat-first AI money coach for younger US users, with a
  "Roast" personality, voice and memory. It offers cash advances, credit
  building and automated "Save Hacks". Autopilot, on a waitlist, recommends
  actions and carries them out "always with your consent". After an
  unexpected medical bill, its Daily Plan "adjusts with a new safe-to-spend
  figure and corrective steps".
- **Similar to LifeCFO in.** This is the closest competitor: an agent that
  acts with consent, and automatic replanning after an emergency.
- **Leaves open.** Optimization across several goals with deadlines is not
  documented, and there are no user what-if scenarios. Gamification is a
  weekly quiz with prize-draw tokens, with no streaks found and nothing that
  adapts to hardship. Not available in Thailand.
- **How LifeCFO differs.** It has competing goals with deadlines and
  priorities, three strategies with explained trade-offs, user-run stress
  tests, and a streak that is protected after a confirmed shock.
- **Sources (opened 18 Oct 2026).**
  [Introducing Autopilot](https://web.meetcleo.com/blog/introducing-autopilot) (rechecked directly),
  [What is Autopilot](https://web.meetcleo.com/faqs/en/articles/13727802-what-is-autopilot),
  [Save Hacks](https://web.meetcleo.com/faqs/en/articles/9966197-how-do-save-hacks-work),
  [Cleo 3.0](https://web.meetcleo.com/blog/Introducing-cleo-3-0),
  [Money IQ](https://web.meetcleo.com/faqs/en/articles/11778095-money-iq),
  [UK availability](https://web.meetcleo.com/faqs/en/articles/12992410-what-s-available-for-cleo-customers-in-the-uk),
  [Pricing](https://web.meetcleo.com/pricing) (5.99 to 14.99 USD a month).

### MAKE by KBank (Thailand)

- **What it does.** A free Kasikornbank e-savings app built around "Cloud
  Pockets": shareable, lockable sub-pockets for budgets and goals, including
  "Wishlist" pockets that work out a monthly amount. Strong gamification:
  consecutive-saving tracking, a habits score, stamps, coins, badges and a
  lottery-style mission.
- **Similar to LifeCFO in.** Envelope-style pockets per goal; streaks; Thai
  users.
- **Leaves open.** Up to 20 scheduled transfers set by hand, so no
  optimization. No AI features were found ("Cloud Chat" is a chat-style
  transaction view). No stress testing or replanning was found.
- **How LifeCFO differs.** It adds the planning, stress-testing and
  replanning layer on top of the envelope idea, and protects the streak in
  hardship rather than rewarding uninterrupted saving only.
- **Sources (opened 18 Oct 2026).**
  [App Store listing](https://apps.apple.com/app/id1496532821),
  [KBank news, 10 Oct 2023](https://www.kasikornbank.com/en/News/Pages/MAKEbyKBank-.aspx).

## 3. Academic background

| Topic | Key idea in one sentence | Reference | How we use it |
|---|---|---|---|
| Goal-based optimization | Investors hold separate mental accounts per goal, and each can be optimized for its own target | Das, Markowitz, Scheid and Statman (2010), "Portfolio Optimization with Mental Accounts", *JFQA* 45(2), 311–334. [link](https://ideas.repec.org/a/cup/jfinqa/v45y2010i02p311-334_00.html) | One envelope per goal with its own target and ramp |
| Multi-goal optimization | Dynamic programming decides which competing goals to fund fully, partly, or not at all | Das, Ostrov, Radhakrishnan and Srivastav (2022), "Dynamic optimization for multi-goals wealth management", *J. Banking & Finance* 140, 106192. [link](https://ideas.repec.org/a/eee/jbfina/v140y2022ics0378426621001515.html) | Supports optimizing across goals rather than filling them one by one; LifeCFO uses a deterministic linear program instead |
| Financial resilience and emergency savings | About half of US respondents could probably not raise 2,000 USD in 30 days, a sign of widespread fragility | Lusardi, Schneider and Tufano (2011), "Financially Fragile Households: Evidence and Implications", *Brookings Papers on Economic Activity*. [link](https://www.brookings.edu/bpea-articles/financially-fragile-households-evidence-and-implications/) | Motivates putting the reserve and liquidity first |
| Stress testing | Household balance sheets can be stress-tested against income, interest-rate and price shocks | Ampudia, van Vlokhoven and Żochowski (2016), "Financial fragility of euro area households", *J. Financial Stability* 27, 250–262. [link](https://ideas.repec.org/a/eee/finsta/v27y2016icp250-262.html) | ShockProof applies the same idea to one household's daily cash flow |
| Agentic decision support in finance | LLM financial advice faces challenges of domain expertise, trustworthiness and ethics, and regulatory conformity | Lo and Ross (2024), "Can ChatGPT Plan Your Retirement?: Generative AI and Financial Advice", *Harvard Data Science Review*. [link](https://hdsr.mitpress.mit.edu/pub/jnml28pl); IOSCO (2025), *AI in Capital Markets* consultation report. [link](https://iosco.org/news/pdf/IOSCONEWS761.pdf) | The LLM never calculates money; numbers it states must come from tools; it cannot approve |
| Behavioural economics of saving | Pre-committing to save out of future raises greatly increased saving rates | Thaler and Benartzi (2004), "Save More Tomorrow", *J. Political Economy* 112(S1), S164–S187. [link](https://ideas.repec.org/a/ucp/jpolec/v112y2004is1ps164-s187.html) | Background for small, regular missions; not tested in LifeCFO |
| Responsible gamification | Gamification's effect on financial behaviour depends on the user's app expertise | Bayuk and Altobello (2019), "Can gamification improve financial behavior?", *Int. J. Bank Marketing* 37(4). [link](https://www.emerald.com/insight/content/doi/10.1108/IJBM-04-2018-0086/full/html) | Rewards never touch money and can be switched off |

No peer-reviewed source was found on gamification that adapts during
financial hardship. That is a gap in the literature, not evidence that it
works.

### Thai context

| Fact | Source | Note |
|---|---|---|
| Household debt was 85.9 % of GDP in Q1 2026 | [SCB EIC flash, 23 Jul 2026](https://www.scbeic.com/en/detail/file/product/10147/hknkoi227d/Flash-Household-debt-JUL-EN-20260723.pdf), citing the Bank of Thailand | Secondary source quoting BOT data |
| 86.7 % of GDP in Q4 2025 | [The Nation, 3 Apr 2026](https://www.nationthailand.com/business/economy/40064614), citing the BOT | Secondary source |
| 77.3 % of Thais have emergency savings covering less than six months | [Khaosod English, 27 Feb 2026](https://www.khaosodenglish.com/tech/2026/02/27/most-thais-lack-six-month-emergency-savings-bot-says/), reporting a BOT survey | The primary BOT report was not opened; check before quoting in the deck |

## 4. What we can and cannot claim

- **Supported by the evidence above.** Among the apps reviewed, none documents
  an optimizer that shares money across competing goals with deadlines under
  a daily cash constraint. None of the five Western apps links Thai bank
  accounts. Cleo is the only one that documents automatic replanning after an
  emergency, and it is on a waitlist. MAKE by KBank has streaks but no
  documented hardship protection.
- **Supported by our own repository.** On 40 seeded synthetic scenarios,
  LifeCFO had no missed essential payment wherever a plan existed
  ([EVALUATION_RESULTS.md](testing/EVALUATION_RESULTS.md)), and 10 of 10
  prompt-injection attempts moved no money.
- **Our hypothesis, not yet tested.** That explained trade-offs help users
  choose better plans, and that a protected streak keeps users engaged
  through an emergency.
- **Do not claim** that rewards improve long-term financial behaviour (there
  is no user study), that LifeCFO is "the first" or "the only" app with a
  feature (we reviewed six apps, not the market), or anything about real
  bank integration (LifeCFO uses a sandbox with synthetic data only).

## 5. Not verified

- Monarch Plus and MAKE Max prices.
- Whether Rocket Money offers any forecasting.
- Goal priorities and deadlines in Origin.
- Gamification in Monarch, YNAB, Origin and Rocket Money: none was found.
- How Cleo links bank accounts (implied by its transaction analysis).
- The primary BOT documents behind the Thai figures.
