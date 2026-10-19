"""Capture the emergency-expense walkthrough of the web app as evidence screenshots.

Optional tool, not part of the test suite. It drives a running app with
Playwright, saves numbered screenshots to docs/competition/evidence/screenshots/,
and saves the app's own audit log export as docs/competition/evidence/web_app_audit_log.json.

    # terminal 1: a fresh sandbox
    LIFECFO_DB_PATH=/tmp/lifecfo-evidence.db uv run streamlit run app/main.py
    # terminal 2 (Playwright is not a project dependency)
    pip install playwright && playwright install chromium
    python scripts/capture_evidence_screenshots.py [--url http://localhost:8501]

Set PLAYWRIGHT_CHROMIUM to use a Chromium binary that is already installed.
It follows the same story as steps 1 to 15 of scripts/demo_15_steps.py: a plan is
approved and executed, income falls 20%, a 10,000 THB repair bill is simulated and
then confirmed, the reserve is drawn down, and a recovery plan is approved.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "competition" / "evidence" / "screenshots"
EXPENSE_DUE_DAY = "12"  # due 12 November 2026, the same bill as step 10 of scripts/demo_15_steps.py
RESERVE_WITHDRAWAL = "6000"  # what the position report asks for (step 11)
CHAT_BOX = "Ask about your plan, goals, bills, or a what-if"


def settle(page: Page) -> None:
    page.wait_for_timeout(600)
    try:
        page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden", timeout=30_000)
    except Exception:  # noqa: BLE001 - the widget may never appear on fast reruns
        pass
    page.wait_for_timeout(800)


def view(page: Page, name: str) -> None:
    page.get_by_role("radio", name=name, exact=True).first.click()
    settle(page)
    page.evaluate("() => (document.querySelector('[data-testid=stMain]')"
                  "|| document.scrollingElement).scrollTo(0, 0)")
    page.wait_for_timeout(300)


def click(page: Page, locator) -> None:
    locator.scroll_into_view_if_needed()
    locator.click()
    settle(page)


def shot(page: Page, name: str, locator=None) -> None:
    path = OUT / f"{name}.png"
    if locator is not None:
        locator.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        locator.screenshot(path=str(path))
    else:
        page.screenshot(path=str(path))
    print(f"saved {path.relative_to(OUT.parents[3])}")


def chat(page: Page, prompt: str) -> None:
    box = page.get_by_placeholder(CHAT_BOX)
    before = page.get_by_text("Answered by:").count()
    box.fill(prompt)
    box.press("Enter")
    page.wait_for_function(
        "n => [...document.querySelectorAll('[data-testid=stCaptionContainer]')]"
        ".filter(e => e.innerText.includes('Answered by')).length > n", arg=before)
    settle(page)


def main(url: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM")
        browser = p.chromium.launch(executable_path=executable) if executable \
            else p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1600})
        page.set_default_timeout(60_000)
        page.goto(url)
        page.get_by_role("radio", name="Home", exact=True).wait_for(timeout=120_000)
        settle(page)

        shot(page, "01-home-before")

        # A plan is generated, approved by the user, and executed.
        view(page, "Personal CFO")
        shot(page, "02-three-validated-plans")
        click(page, page.get_by_role("radio", name="Balanced", exact=True))
        click(page, page.get_by_role("button", name="Request approval for the Balanced plan"))
        view(page, "Sandbox")
        click(page, page.get_by_role("button", name="Approve"))
        click(page, page.get_by_role("button", name="Execute in sandbox"))
        shot(page, "03-user-approves-and-executes")

        # Income falls 20%: the user confirms it and approves a new plan.
        click(page, page.get_by_role("button", name="Confirm this income change"))
        view(page, "Personal CFO")
        shot(page, "04-new-plans-after-income-cut")
        click(page, page.get_by_role("button", name="Request approval for the Safety First plan"))
        view(page, "Sandbox")
        click(page, page.get_by_role("button", name="Approve"))
        click(page, page.get_by_role("button", name="Execute in sandbox"))

        # An emergency: first a what-if in the chat, then the user confirms the bill.
        view(page, "AI CFO chat")
        chat(page, "What if I get a 10,000 THB repair bill?")
        last = page.locator('[data-testid="stChatMessage"]').last
        last.evaluate("e => e.scrollIntoView({block: 'start'})")
        page.wait_for_timeout(500)
        shot(page, "05-ai-what-if-repair-bill")

        view(page, "Sandbox")
        day = page.get_by_role("spinbutton", name="day, Due on")
        day.click()
        day.press_sequentially(EXPENSE_DUE_DAY)
        page.keyboard.press("Tab")
        settle(page)
        click(page, page.get_by_role("button", name="Confirm this expense"))
        view(page, "Sandbox")
        shot(page, "06-user-confirms-the-expense")

        view(page, "Personal CFO")
        shot(page, "07-reserve-needed-before-replanning")

        view(page, "Sandbox")
        amount = page.get_by_label("Withdraw from the emergency reserve (THB)")
        amount.scroll_into_view_if_needed()
        amount.fill(RESERVE_WITHDRAWAL)
        click(page, page.locator('[data-testid="stFormSubmitButton"] button')
              .filter(has_text="Withdraw"))

        # The recovery plan, its effect on each goal, and the reasons.
        view(page, "Personal CFO")
        shot(page, "08-recovery-plans-and-affected-goals")
        click(page, page.get_by_role("button", name="Request approval for the Safety First plan"))
        view(page, "Sandbox")
        click(page, page.get_by_role("button", name="Approve"))
        click(page, page.get_by_role("button", name="Execute in sandbox"))
        shot(page, "09-recovery-plan-executed")
        page.get_by_text("Audit log", exact=True).last.evaluate(
            "e => e.scrollIntoView({block: 'start'})")
        page.wait_for_timeout(500)
        shot(page, "10-audit-log")
        with page.expect_download() as download:
            page.get_by_role("button", name="Download audit log (JSON)").click()
        log_path = OUT.parent / "web_app_audit_log.json"
        download.value.save_as(log_path)
        print(f"saved {log_path.relative_to(OUT.parents[3])}")

        view(page, "Home")
        shot(page, "11-home-after")
        browser.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[args.index("--url") + 1] if "--url" in args else "http://localhost:8501")
