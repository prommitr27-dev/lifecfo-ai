# คู่มือ Member 1 (ฝั่งโค้ด)

สิ่งที่ต้องรู้เพื่อแก้หรือต่อยอดโค้ดโดยไม่ทำให้กติกาการเงินพัง อัปเดต 15 ต.ค. 2026 (commit `f628ed2`, test 258 ตัว)

## 1. คำสั่งที่ใช้บ่อย

```bash
uv sync                                   # ติดตั้ง dependency
uv run pytest                             # test ทั้งหมด ต้องผ่านก่อน commit
uv run ruff check .                       # lint ต้องผ่านก่อน commit
uv run streamlit run app/main.py          # เปิดแอป
uv run python scripts/demo_offline.py --write    # demo offline + หลักฐานส่งประกวด
uv run python scripts/manual_scenarios.py        # รายงาน manual scenario 6 ชุด
```

- ค่าเริ่มต้นไม่ใช้ LLM และไม่ต่อเน็ต ถ้าจะใช้ Groq ตั้งในไฟล์ `.env` (ดู `docs/AI_PROVIDERS.md`)
- ฐานข้อมูล sandbox ของแอปอยู่ที่ `.lifecfo/sandbox.db` (git ไม่เก็บ) ลบไฟล์นี้หรือกด Reset ในหน้า Sandbox เพื่อเริ่มใหม่
- Test ทุกตัวใช้ฐานข้อมูลชั่วคราวและบังคับโหมด offline เอง ไม่ยุ่งกับ `.env` หรือ sandbox ของคุณ

## 2. โครงสร้าง: อะไรอยู่ที่ไหน

```
app/main.py              หน้าจอ Streamlit 5 หน้า (Cash flow, Personal CFO, AI CFO chat, Rewards, Sandbox)
lifecfo/domain/          โมเดลข้อมูล (Pydantic, frozen), เงินเป็นสตางค์, clock, loader ของ YAML
lifecfo/cashflow/        forecast รายวัน, feasibility, position (เงินว่าง, deficit, buffer, reserve)
lifecfo/debt/            ดอกเบี้ย, ตารางผ่อน, Avalanche/Snowball, แบ่งเงินจ่ายหนี้เพิ่ม
lifecfo/optimization/    LP ของ 3 กลยุทธ์, validate_plan, apply_plan, เหตุผลที่เป้าช้า
lifecfo/services/        SandboxService: ทางเดียวที่แก้ state ได้
lifecfo/database/        SQLite: state, plans, approvals, transactions, audit, rewards
lifecfo/rewards/         XP, ภารกิจ, badge, streak state machine
lifecfo/agents/          tool registry (tier), views (ผลคำนวณเป็นข้อมูล), explain (เป็นข้อความ), agent
lifecfo/llm/             client ของ Gemini/Groq/Ollama/custom ผ่าน API แบบ OpenAI
config/                  ค่าที่ทีมเศรษฐศาสตร์ปรับเอง (weights, reward rules, risk thresholds)
data/synthetic/          โปรไฟล์ทดสอบ (profile_demo, profile_debt_demo)
tests/                   unit, integration (แอป), scenarios (acceptance AT1 ถึง AT16)
```

## 3. ข้อมูลไหลอย่างไร

```
YAML profile → FinancialState (frozen)
   → engines (pure function, ไม่แตะ DB): forecast, position, debt, optimizer
   → views.py แปลงผลเป็น dict หน่วยบาท → explain.py เรียบเรียงเป็นข้อความ
   → agent (offline router หรือ LLM) เรียกได้เฉพาะผ่าน tool registry

การเปลี่ยน state จริงมีทางเดียว: SandboxService
   propose → decide (USER เท่านั้น) → execute → advance
   confirm_expense / withdraw_reserve (USER เท่านั้น)
   ทุกขั้นเขียน audit log แบบ hash chain และส่ง event ให้ RewardsService
```

## 4. กติกาที่ห้ามทำพัง

ถ้าแก้โค้ดแล้ว test ในคอลัมน์ขวาแดง แปลว่าละเมิดกติกา ให้หาสาเหตุ ไม่ใช่แก้ test ให้ผ่าน

| # | กติกา | มาจาก | Test ที่เฝ้าอยู่ |
|---|---|---|---|
| 1 | เงินเป็นสตางค์ (int) เสมอ ห้ามใช้ float กับยอดเงิน | ออกแบบ | `test_domain.py` |
| 2 | Engine เป็น pure function ห้ามแก้ state ที่รับเข้ามา และห้ามเขียน DB | ออกแบบ | `test_forecast_does_not_mutate_state`, `test_tools_never_change_the_state` |
| 3 | นับเงินครั้งเดียว: เงินสดแบ่งเป็นซอง ผลรวมซอง = ยอดบัญชี การโอนเข้าซองไม่เปลี่ยนเงินรวม เงินในซองเป้าหมายไม่ถูกนับเป็นเงินว่าง | 3.1, AT6 | `test_total_cash_changes_only_by_income_and_spending`, `test_at6_*` |
| 4 | ค่าใช้จ่ายจำเป็นและหนี้ขั้นต่ำห้ามถูกลด ถ้าจ่ายไม่ไหวต้องรายงาน ไม่สร้างแผน | D2, AT3 | `test_at3_*`, `test_no_plan_is_invented_*` |
| 5 | แสดงสถานะเดิมของผู้ใช้ก่อนเสนอแผนเสมอ | D2, AT2 | `test_at2_*` |
| 6 | Flexible ลดได้เฉพาะเมื่อผู้ใช้อนุญาต และไม่ต่ำกว่าขั้นต่ำของผู้ใช้ | D1, AT1 | `test_at1_*` |
| 7 | Buffer กับเงินสำรองตรวจกับเงินก้อนเดียวกัน ห้ามบวกกัน | D3, D4 | `test_at4_*`, `test_at6_*` |
| 8 | ไม่รู้ดอกเบี้ยห้ามถือเป็น 0% และต้องติดป้าย CONTRACT_BASED / ESTIMATED / UNAVAILABLE | D5, AT7 | `test_at7_*` |
| 9 | ห้ามเลื่อน deadline, เปลี่ยนเป้า หรือเปลี่ยน priority เอง | D7, AT9, AT14 | `test_at9_*`, `test_at14_deadline_is_never_silently_extended` |
| 10 | แผนทุกแผนต้องผ่าน `validate_plan` ก่อนแสดงและก่อน execute | 8, 3.4 | `test_validator_rejects_*`, `test_random_profiles_*` |
| 11 | แผนที่เสนอไม่ใช่แผนที่อนุมัติ มีแต่ปุ่มในแอปที่อนุมัติได้ ไม่มี tool ไหนอนุมัติได้ | 3.5, AT16 | `test_agent_cannot_approve`, `test_no_tool_lets_the_agent_approve` |
| 12 | Approval ผูกกับ hash ของแผนและ state ใช้ได้ครั้งเดียว execute ซ้ำไม่เกิดผล | AT16 | `test_duplicate_execution_changes_nothing`, `test_tampered_*` |
| 13 | ตัวเลขทุกตัวในคำตอบของ LLM ต้องมาจากผล tool ไม่งั้นใช้คำตอบ offline แทน | 3.4 | `test_invented_figures_*` |
| 14 | XP ไม่มีผลกับเงินหรือแผน, รางวัลไม่ซ้ำ, ปิดแล้วไม่บันทึก | Rewards | `test_rewards.py` |
| 15 | ห้ามใส่ข้อมูลการเงินจริง, key หรือ `.env` ลง git | 9 | `.gitignore` |

## 5. ถ้าจะเพิ่มของใหม่

- **Tool ใหม่ให้ agent**: เพิ่ม input model และ handler ใน `lifecfo/agents/tools.py`, ลงทะเบียนใน `default_registry()` พร้อม tier ที่ต่ำที่สุดที่พอ, เพิ่ม renderer ใน `explain.py` และคำค้นใน `_INTENTS` ของ `agent.py` ถ้าอยากให้ agent offline เรียกได้ แล้วอัปเดตชุดชื่อ tool ใน `test_no_tool_lets_the_agent_approve`
- **การคำนวณใหม่**: เขียนเป็น pure function ใน package ที่ตรงเรื่อง ส่งผลเป็นสตางค์ ให้ `views.py` แปลงเป็นบาท ห้ามคำนวณใน `explain.py`
- **สิ่งที่เปลี่ยน state**: เพิ่มเป็น method ใน `SandboxService` เท่านั้น ต้องเช็ก actor, เขียน audit, และถ้าเปลี่ยนเงินต้องมี transaction row
- **Provider LLM ใหม่**: ถ้าเป็น API แบบ OpenAI ใช้โหมด `custom` ไม่ต้องแก้โค้ด ถ้าไม่ใช่ ให้เขียน class ที่มี method `complete` ตาม `LLMClient`
- **ค่าตัวเลขที่เป็นสมมติฐาน**: ใส่ใน `config/*.yaml` ไม่ hard-code และเขียนที่มาไว้ใน docs

## 6. งานที่ค้าง และจะเสียบเข้าตรงไหน

| งาน | สถานะ | ที่ที่ต้องแก้ |
|---|---|---|
| M7 สคริปต์ demo 15 ขั้นตามบรีฟ | ถัดไป | ต่อจาก `scripts/demo_offline.py` |
| หน้าอนุมัติการเปลี่ยนค่าที่ผู้ใช้ตั้ง (เลื่อน deadline, buffer, flexible) | ยังไม่มี ตอนนี้ระบบแค่เสนอ ผู้ใช้แก้โปรไฟล์เอง | method ใหม่ใน `SandboxService` คู่กับประเภท proposal ใหม่ใน `database/store.py` และปุ่มในหน้า Sandbox |
| วิธีคิดดอกเบี้ยตามสัญญาแบบอื่น | มี 2 วิธี | `InterestMethod` ใน `domain/models.py` และ `_accrue` ใน `debt/schedule.py` |
| คำถาม 6 ข้อถึงทีมเศรษฐศาสตร์ | รอคำตอบ | ส่วนใหญ่แก้ที่ `config/strategy_weights.yaml` หรือ `optimizer.py` ดูข้อ 4 ของ `docs/financial_model/RULES_V0.2_STATUS.md` |
| ค่าร่างของ rewards (grace 1 วัน, คุ้มครอง 14 วัน, ค่า XP) | รอทีมยืนยัน | `config/reward_rules.yaml` |
| M9 evaluation: scenario 30 ถึง 50 ชุดเทียบ baseline | ยังไม่เริ่ม | `lifecfo/evaluation/` (ใหม่) และ `data/scenarios/` จาก Member 3 |
| M10 เอกสารส่งประกวด, deck, วิดีโอ, security self-assessment | ยังไม่เริ่ม | `docs/competition/` ใช้ `docs/SECURITY_DESIGN.md` เป็นต้นทาง |

## 7. วิธีทำงานกับ repo

- `main` ต้องผ่าน CI เสมอ ก่อน commit ให้รัน `uv run ruff check .` และ `uv run pytest`
- ข้อความ commit เป็นภาษาอังกฤษ และไม่ใส่ชื่อ Claude เป็นผู้ร่วมเขียน
- ห้าม force-push เว้นแต่ตกลงกันในทีม
- ถ้าใช้ Claude Code ในโฟลเดอร์นี้ มันจะถามก่อนว่าคุณเป็น Member คนไหน (`CLAUDE.md`)
- เอกสารอ้างอิงหลัก: `docs/architecture/SYSTEM_ARCHITECTURE.md`, `docs/SECURITY_DESIGN.md`, `docs/financial_model/RULES_V0.2_STATUS.md`, `docs/REWARDS_SYSTEM.md`
