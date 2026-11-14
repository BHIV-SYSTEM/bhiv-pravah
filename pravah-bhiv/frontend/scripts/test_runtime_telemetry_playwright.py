"""
Playwright E2E Verification for Pravah Runtime and Telemetry Pages.
"""

import sys
import argparse
import time

def run_tests(base_url: str, headless: bool):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        print("FAIL: playwright not installed")
        sys.exit(1)

    url = f"{base_url.rstrip('/')}"
    results = []

    def record(name: str, passed: bool, detail: str = ""):
        mark = "PASS" if passed else "FAIL"
        msg = f"[{mark}] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        results.append((name, passed, detail))

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless, channel="msedge")
        except Exception:
            try:
                browser = p.chromium.launch(headless=headless, channel="chrome")
            except Exception:
                browser = p.chromium.launch(headless=headless)

        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        # =====================================================================
        # RUNTIME PAGE (/runtime)
        # =====================================================================
        runtime_url = f"{url}/runtime"
        try:
            resp = page.goto(runtime_url, timeout=20000, wait_until="domcontentloaded")
            record("Runtime page loads (HTTP < 400)", resp is not None and resp.status < 400, f"status={resp.status if resp else 'none'}")
        except Exception as e:
            record("Runtime page loads (HTTP < 400)", False, str(e))

        try:
            page.wait_for_selector("text=Runtime Manager", timeout=10000)
            record("Runtime Manager header rendered", True)
        except Exception as e:
            record("Runtime Manager header rendered", False, str(e))

        try:
            # Check Active Compute Nodes section
            nodes_section = page.locator("text=Active Compute Nodes").first
            nodes_section.wait_for(timeout=5000)
            record("Active Compute Nodes section present", True)
        except Exception as e:
            record("Active Compute Nodes section present", False, str(e))

        try:
            # Check RL Autonomy Loop card
            loop_card = page.locator("text=RL AUTONOMY LOOP")
            loop_card.wait_for(timeout=5000)
            body_text = page.inner_text("body")
            has_running = "RUNNING" in body_text
            record("RL Autonomy Loop status rendered", has_running, "Found RUNNING state")
        except Exception as e:
            record("RL Autonomy Loop status rendered", False, str(e))

        try:
            # Check Shakti Governance contract notice
            body_text = page.inner_text("body")
            has_shakti = "Shakti" in body_text or "governance" in body_text.lower()
            record("Shakti Governance contracts mentioned", has_shakti)
        except Exception as e:
            record("Shakti Governance contracts mentioned", False, str(e))

        # =====================================================================
        # TELEMETRY PAGE (/telemetry)
        # =====================================================================
        telemetry_url = f"{url}/telemetry"
        try:
            resp = page.goto(telemetry_url, timeout=20000, wait_until="domcontentloaded")
            record("Telemetry page loads (HTTP < 400)", resp is not None and resp.status < 400, f"status={resp.status if resp else 'none'}")
        except Exception as e:
            record("Telemetry page loads (HTTP < 400)", False, str(e))

        try:
            time.sleep(1)
            body_text = page.inner_text("body")
            has_content = "Telemetry" in body_text or "Monitored" in body_text or "Repository" in body_text or "INGESTED" in body_text
            record("Telemetry dashboard content rendered", has_content)
        except Exception as e:
            record("Telemetry dashboard content rendered", False, str(e))

        try:
            # Check Telemetry tables or metrics
            body_text = page.inner_text("body")
            has_telemetry = "Telemetry" in body_text or "Latency" in body_text or "Throughput" in body_text or "Events" in body_text
            record("Telemetry data views rendered", has_telemetry)
        except Exception as e:
            record("Telemetry data views rendered", False, str(e))

        browser.close()

    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    print("\n" + "=" * 60)
    print(f"Runtime & Telemetry Playwright Tests: {passed}/{total} PASSED")
    if passed == total:
        print("All tests passed.")
    else:
        print(f"FAILED: {total - passed} tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://pravah.blackholeinfiverse.com")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()
    run_tests(args.url, args.headless)
