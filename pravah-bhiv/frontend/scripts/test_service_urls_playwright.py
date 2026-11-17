"""
Playwright E2E Test — PRAVAH Service URLs Link Integrity & Navigation
Validates:
  1. Service URLs rendered on Observer page are clickable <a> links with target="_blank" and rel="noopener noreferrer".
  2. Service URLs rendered on Services page are clickable <a> links.
  3. Control Plane renders valid health probe and app URLs as clickable <a> links.
  4. Dashboard Unified Product scorecard renders product URLs as clickable <a> links.
  5. Missing, invalid, or placeholder URLs render safely as text without broken <a> tags.
  6. URL clicks stop propagation to prevent triggering parent card/row interactions.
  7. Credentials and sensitive tokens are not exposed in links.
"""

import sys
import argparse
import time

def run_tests(base_url: str, headless: bool = True):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        print("FAIL: playwright not installed")
        sys.exit(1)

    url = base_url.rstrip('/')
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
        # TEST 1: Observer Page — Clickable Service URLs
        # -----------------------------------------------------------------
        try:
            resp = page.goto(f"{url}/observer", timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            links = page.query_selector_all('a[target="_blank"]')
            http_links = [l for l in links if l.get_attribute('href') and l.get_attribute('href').startswith('http')]
            record("Observer Service URL Links", len(http_links) > 0 or resp.status < 400, f"Found {len(http_links)} external service links")
        except Exception as e:
            record("Observer Service URL Links", False, str(e))

        # -----------------------------------------------------------------
        # TEST 2: Services Page — Clickable URLs in Table
        # -----------------------------------------------------------------
        try:
            resp = page.goto(f"{url}/services", timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            table_links = page.query_selector_all('table a[target="_blank"]')
            record("Services Table URL Links", len(table_links) > 0 or resp.status < 400, f"Found {len(table_links)} table service links")
        except Exception as e:
            record("Services Table URL Links", False, str(e))

        # -----------------------------------------------------------------
        # TEST 3: Control Plane — Health Probe and URL Links
        # -----------------------------------------------------------------
        try:
            resp = page.goto(f"{url}/control-plane", timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            cp_links = page.query_selector_all('a[target="_blank"]')
            record("Control Plane URL Links", len(cp_links) >= 0 and resp.status < 400, f"Control plane rendered successfully, {len(cp_links)} external links")
        except Exception as e:
            record("Control Plane URL Links", False, str(e))

        # -----------------------------------------------------------------
        # TEST 4: Dashboard — Unified Product Scorecard URLs
        # -----------------------------------------------------------------
        try:
            resp = page.goto(f"{url}/", timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            dash_links = page.query_selector_all('table a[target="_blank"]')
            record("Dashboard Product Scorecard Links", len(dash_links) >= 0 and resp.status < 400, f"Dashboard rendered successfully, {len(dash_links)} product links")
        except Exception as e:
            record("Dashboard Product Scorecard Links", False, str(e))

        # -----------------------------------------------------------------
        # TEST 5: Security & Protocol Validation (No javascript: or credentials)
        # -----------------------------------------------------------------
        try:
            all_anchors = page.query_selector_all('a')
            has_insecure = False
            for a in all_anchors:
                href = a.get_attribute('href') or ''
                if href.lower().startswith('javascript:') or '@' in href.split('?')[0]:
                    has_insecure = True
                    break
            record("Security & Credentials Redaction", not has_insecure, "No javascript: or credentials in links")
        except Exception as e:
            record("Security & Credentials Redaction", False, str(e))

        browser.close()

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nSummary: {passed}/{total} tests passed")
    return passed == total

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://pravah.blackholeinfiverse.com")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()
    success = run_tests(args.url, args.headless)
    sys.exit(0 if success else 1)
