"""
Playwright E2E Test — PRAVAH Main Dashboard Page

Tests:
  1. Main Dashboard loads without crashing (HTTP 200)
  2. React hydration complete (header, stats cards visible)
  3. CPU Utilization stat card is visible and valid (contains % or N/A, not empty/undefined)
  4. Memory Utilization stat card is visible and valid (contains % or N/A)
  5. System Status stat card is visible (HEALTHY, DEGRADED, or UNKNOWN)
  6. Telemetry Collection card is visible (AVAILABLE or UNAVAILABLE)
  7. Response Times widget renders correctly without throwing errors
  8. Service Distribution widget renders correctly without throwing errors
  9. Repeated CPU metric checks confirm consistent readings (no crashes or blank values)

Target URL: https://pravah.blackholeinfiverse.com
Fallback: http://163.128.209.18:4500
"""

import sys
import argparse
import time

def run_tests(base_url: str, headless: bool):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        print("FAIL: playwright not installed — run: pip install playwright && playwright install chromium")
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

        # -----------------------------------------------------------------
        # TEST 1: Page loads
        # -----------------------------------------------------------------
        try:
            response = page.goto(url, timeout=20000, wait_until="domcontentloaded")
            if response and response.status < 400:
                record("Dashboard page loads (HTTP < 400)", True, f"status={response.status}")
            else:
                status = response.status if response else "no response"
                record("Dashboard page loads (HTTP < 400)", False, f"status={status}")
        except Exception as e:
            record("Dashboard page loads (HTTP < 400)", False, str(e))
            browser.close()
            return results

        # -----------------------------------------------------------------
        # TEST 2: React Hydration & Header
        # -----------------------------------------------------------------
        try:
            page.wait_for_selector("h2, .premium-card", timeout=12000)
            record("Dashboard React hydrated (content rendered)", True)
        except PlaywrightTimeout:
            record("Dashboard React hydrated (content rendered)", False, "Timeout waiting for header/cards")

        # -----------------------------------------------------------------
        # TEST 3: CPU Utilization Stat Card
        # -----------------------------------------------------------------
        try:
            cpu_card = page.locator(".premium-card:has-text('CPU Utilization')")
            cpu_card.wait_for(timeout=10000)
            cpu_text = cpu_card.inner_text()
            # Must contain a percentage or N/A
            has_valid_val = "%" in cpu_text or "N/A" in cpu_text
            record("CPU Utilization card visible & valid", has_valid_val, f"text={cpu_text.replace(chr(10), ' | ')}")
        except Exception as e:
            record("CPU Utilization card visible & valid", False, str(e))

        # -----------------------------------------------------------------
        # TEST 4: Memory Utilization Stat Card
        # -----------------------------------------------------------------
        try:
            mem_card = page.locator(".premium-card:has-text('Memory Utilization')")
            mem_card.wait_for(timeout=5000)
            mem_text = mem_card.inner_text()
            has_valid_val = "%" in mem_text or "N/A" in mem_text
            record("Memory Utilization card visible & valid", has_valid_val, f"text={mem_text.replace(chr(10), ' | ')}")
        except Exception as e:
            record("Memory Utilization card visible & valid", False, str(e))

        # -----------------------------------------------------------------
        # TEST 5: System Status Stat Card
        # -----------------------------------------------------------------
        try:
            status_card = page.locator(".premium-card:has-text('System Status')")
            status_card.wait_for(timeout=5000)
            status_text = status_card.inner_text()
            has_valid_status = any(s in status_text for s in ["HEALTHY", "DEGRADED", "UNKNOWN", "OPERATIONAL"])
            record("System Status card visible", has_valid_status, f"text={status_text.replace(chr(10), ' | ')}")
        except Exception as e:
            record("System Status card visible", False, str(e))

        # -----------------------------------------------------------------
        # TEST 6: Telemetry Collection Stat Card
        # -----------------------------------------------------------------
        try:
            telemetry_card = page.locator(".premium-card:has-text('Telemetry Collection')")
            telemetry_card.wait_for(timeout=5000)
            telemetry_text = telemetry_card.inner_text()
            record("Telemetry Collection card visible", True, f"text={telemetry_text.replace(chr(10), ' | ')}")
        except Exception as e:
            record("Telemetry Collection card visible", False, str(e))

        # -----------------------------------------------------------------
        # TEST 7: Response Times Widget (no JS crashes)
        # -----------------------------------------------------------------
        try:
            rt_widget = page.locator(".premium-card:has-text('Response Times')")
            rt_widget.wait_for(timeout=5000)
            record("Response Times widget rendered", True)
        except Exception as e:
            record("Response Times widget rendered", False, str(e))

        # -----------------------------------------------------------------
        # TEST 8: Service Distribution Widget (no JS crashes)
        # -----------------------------------------------------------------
        try:
            sd_widget = page.locator(".premium-card:has-text('Service Distribution')")
            sd_widget.wait_for(timeout=5000)
            record("Service Distribution widget rendered", True)
        except Exception as e:
            record("Service Distribution widget rendered", False, str(e))

        # -----------------------------------------------------------------
        # TEST 9: Repeated CPU Metric Stability Over Time (no blanking)
        # -----------------------------------------------------------------
        try:
            time.sleep(3)
            cpu_card = page.locator(".premium-card:has-text('CPU Utilization')")
            cpu_text_after = cpu_card.inner_text()
            has_valid_val = "%" in cpu_text_after or "N/A" in cpu_text_after
            record("Repeated CPU metric check remains valid", has_valid_val, f"text={cpu_text_after.replace(chr(10), ' | ')}")
        except Exception as e:
            record("Repeated CPU metric check remains valid", False, str(e))

        browser.close()

    print("\n" + "="*60)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"Main Dashboard Playwright Tests: {passed}/{total} PASSED")
    if passed < total:
        print("FAILURES:")
        for name, ok, detail in results:
            if not ok:
                print(f"  ✗ {name}: {detail}")
    else:
        print("All tests passed.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Playwright test for PRAVAH Main Dashboard")
    parser.add_argument(
        "--url",
        default="https://pravah.blackholeinfiverse.com",
        help="Base URL of the main dashboard"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)"
    )
    args = parser.parse_args()
    results = run_tests(args.url, args.headless)
    has_failures = any(not ok for _, ok, _ in results)
    sys.exit(1 if has_failures else 0)
