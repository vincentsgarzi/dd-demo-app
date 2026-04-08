#!/usr/bin/env python3
"""
RUM Load Generator — Playwright headless browsers simulating real user sessions.

Each user persona has different behaviors, speeds, and error propensity.
Generates real RUM sessions with views, actions, errors, long tasks, and resources.
Session Replay is captured automatically via the RUM SDK.

Usage:
    python rum_loadgen.py                  # default: 3 concurrent users
    python rum_loadgen.py --users 5        # 5 concurrent browsers
    python rum_loadgen.py --users 2 --headful  # visible browsers for debugging
"""

import asyncio
import random
import argparse
import signal
import sys
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"

# ─── User Personas ───────────────────────────────────────────────────────────

PERSONAS = [
    {
        "name": "Alice Chen",
        "email": "alice.chen@acme.com",
        "role": "power_user",
        "speed": "fast",        # 0.5–1.5s between actions
        "patience": 0.9,        # rarely abandons
        "error_prone": False,
        "viewport": {"width": 1440, "height": 900},
        "journeys": ["full_purchase", "search_browse", "full_purchase", "compare_products"],
        "user_agent": None,     # default
    },
    {
        "name": "Bob Martinez",
        "email": "bob.martinez@globex.com",
        "role": "power_user",
        "speed": "fast",
        "patience": 0.95,
        "error_prone": False,
        "viewport": {"width": 1920, "height": 1080},
        "journeys": ["full_purchase", "full_purchase", "admin_check", "search_browse"],
        "user_agent": None,
    },
    {
        "name": "Charlie Kim",
        "email": "charlie.kim@initech.com",
        "role": "casual_browser",
        "speed": "slow",        # 2–5s between actions
        "patience": 0.5,        # often abandons cart
        "error_prone": False,
        "viewport": {"width": 1366, "height": 768},
        "journeys": ["browse_only", "search_browse", "abandon_cart"],
        "user_agent": None,
    },
    {
        "name": "Dana Park",
        "email": "dana.park@waynetech.com",
        "role": "error_magnet",
        "speed": "medium",      # 1–3s between actions
        "patience": 0.7,
        "error_prone": True,    # seeks out broken pages
        "viewport": {"width": 1280, "height": 800},
        "journeys": ["trigger_errors", "rapid_clicks", "trigger_errors", "search_edge_cases"],
        "user_agent": None,
    },
    {
        "name": "Mobile Mo",
        "email": "mo@startup.io",
        "role": "mobile_user",
        "speed": "medium",
        "patience": 0.4,        # very impatient on mobile
        "error_prone": False,
        "viewport": {"width": 390, "height": 844},  # iPhone 14 Pro
        "journeys": ["browse_only", "quick_buy", "browse_only"],
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    },
    {
        "name": "Tab Hoarder Tina",
        "email": "tina.tabs@megacorp.com",
        "role": "power_user",
        "speed": "fast",
        "patience": 0.85,
        "error_prone": False,
        "viewport": {"width": 1440, "height": 900},
        "journeys": ["multi_tab_browse", "full_purchase", "compare_products"],
        "user_agent": None,
    },
]

# ─── Timing helpers ──────────────────────────────────────────────────────────

def delay_for(speed):
    """Return a random delay based on user speed."""
    ranges = {"fast": (0.5, 1.5), "medium": (1.5, 3.0), "slow": (2.5, 5.0)}
    lo, hi = ranges.get(speed, (1.0, 2.5))
    return random.uniform(lo, hi)

def ts():
    return datetime.now().strftime("%H:%M:%S")

# ─── Journey Implementations ────────────────────────────────────────────────

async def journey_browse_only(page, persona):
    """Just browse the homepage and click a few products."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Click on 2-3 random products
    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    for _ in range(random.randint(2, min(4, count))):
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))
        await page.go_back()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.5)


async def journey_full_purchase(page, persona):
    """Browse → add items → checkout → complete order."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Click on a product
    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    # Add 1-3 items
    for _ in range(random.randint(1, 3)):
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        # Click "Add to cart" button
        add_btn = page.locator("button", has_text="Add to cart")
        if await add_btn.count() > 0:
            await add_btn.first.click()
            await asyncio.sleep(0.5)

        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.5)

    # Go to cart
    await page.goto(f"{BASE_URL}/cart")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Proceed to checkout
    subscribe_btn = page.locator("button", has_text="Subscribe")
    if await subscribe_btn.count() > 0:
        await subscribe_btn.first.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        # Fill email and submit
        email_input = page.locator("input[type='email']")
        if await email_input.count() > 0:
            await email_input.fill(persona["email"])
            await asyncio.sleep(0.5)

            submit_btn = page.locator("button[type='submit']")
            if await submit_btn.count() > 0:
                await submit_btn.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(delay_for(persona["speed"]))


async def journey_search_browse(page, persona):
    """Search for products and browse results."""
    queries = ["APM", "monitoring", "security", "logs", "profiler", "rum",
               "cloud", "database", "incident", "synthetics", "nonexistent_xyz"]

    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    for q in random.sample(queries, random.randint(2, 4)):
        await page.goto(f"{BASE_URL}/?q={q}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        # Click first result if any
        cards = page.locator("a[href^='/product/']")
        if await cards.count() > 0:
            await cards.first.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))
            await page.go_back()
            await page.wait_for_load_state("networkidle")


async def journey_trigger_errors(page, persona):
    """Deliberately visit broken pages and trigger JS errors."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Visit product ID 5, 10, 15 (id % 5 === 0 triggers the TypeError)
    for pid in [5, 10, 15]:
        try:
            await page.goto(f"{BASE_URL}/product/{pid}")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))
        except Exception:
            pass  # Page might crash — that's the point

    # Visit cursed product (id=3 triggers 500 on backend)
    try:
        await page.goto(f"{BASE_URL}/product/3")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))
    except Exception:
        pass

    # Visit non-existent product
    try:
        await page.goto(f"{BASE_URL}/product/99999")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))
    except Exception:
        pass

    # Trigger unhandled promise rejection via console
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await page.evaluate("""() => {
        // Simulate a third-party script error
        setTimeout(() => {
            const tracker = window.__analyticsTracker;
            tracker.send('pageview');  // TypeError: Cannot read properties of undefined
        }, 500);
    }""")
    await asyncio.sleep(2)

    # Inject a custom error to simulate ad blocker conflict
    await page.evaluate("""() => {
        setTimeout(() => {
            throw new Error('ChunkLoadError: Loading chunk vendors-analytics failed. (blocked by ad blocker?)');
        }, 300);
    }""")
    await asyncio.sleep(1.5)


async def journey_rapid_clicks(page, persona):
    """Rapid-fire clicks that simulate impatient double/triple clicking."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(0.5)

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    # Rapid click multiple add-to-cart buttons without waiting
    for _ in range(5):
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(0.3)

        add_btn = page.locator("button", has_text="Add to cart")
        if await add_btn.count() > 0:
            # Triple click
            await add_btn.first.click()
            await asyncio.sleep(0.05)
            await add_btn.first.click()
            await asyncio.sleep(0.05)
            await add_btn.first.click()

        await asyncio.sleep(0.3)
        await page.go_back()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(0.2)


async def journey_abandon_cart(page, persona):
    """Add items but leave at checkout — classic abandonment."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Add a couple items
    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    for _ in range(2):
        if count == 0:
            break
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        add_btn = page.locator("button", has_text="Add to cart")
        if await add_btn.count() > 0:
            await add_btn.first.click()
            await asyncio.sleep(0.5)

        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")

    # Go to cart
    await page.goto(f"{BASE_URL}/cart")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]) * 2)  # stares at cart

    # Navigate to checkout
    await page.goto(f"{BASE_URL}/checkout")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Start typing email but abandon (close page / navigate away)
    email_input = page.locator("input[type='email']")
    if await email_input.count() > 0:
        await email_input.fill(persona["email"][:5])  # partial email
        await asyncio.sleep(delay_for(persona["speed"]) * 2)

    # Abandon — go back to homepage
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")


async def journey_quick_buy(page, persona):
    """Mobile fast-buy: tap first product, buy now."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    # Tap first interesting product
    await cards.nth(random.randint(0, min(3, count - 1))).click()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Hit "Buy now" (add to cart + navigate to checkout)
    buy_btn = page.locator("button", has_text="Buy now")
    if await buy_btn.count() > 0:
        await buy_btn.first.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        email_input = page.locator("input[type='email']")
        if await email_input.count() > 0:
            await email_input.fill(persona["email"])
            await asyncio.sleep(0.5)
            submit_btn = page.locator("button[type='submit']")
            if await submit_btn.count() > 0:
                await submit_btn.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(delay_for(persona["speed"]))


async def journey_admin_check(page, persona):
    """Power user checks the admin stats page."""
    await page.goto(f"{BASE_URL}/admin")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]) * 2)  # read the stats

    # Also check orders
    await page.goto(f"{BASE_URL}/orders")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))


async def journey_compare_products(page, persona):
    """Open several product pages to compare them."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count < 2:
        return

    # Click through 4-6 products rapidly (comparison shopping)
    indices = random.sample(range(count), min(6, count))
    for idx in indices:
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.7)
        await page.go_back()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.3)


async def journey_search_edge_cases(page, persona):
    """Search with weird inputs to trigger edge cases."""
    edge_queries = [
        "",                         # empty search
        "a",                        # single char
        "<script>alert(1)</script>",  # XSS attempt
        "'; DROP TABLE products;--",  # SQL injection
        "x" * 500,                    # very long query
        "🐶💥🔥",                     # emoji
    ]

    for q in edge_queries:
        try:
            await page.goto(f"{BASE_URL}/?q={q}")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]) * 0.5)
        except Exception:
            pass


async def journey_multi_tab_browse(page, persona):
    """Open multiple product pages in sequence (simulates tab hoarding)."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Visit 8+ product pages in rapid succession
    for pid in random.sample(range(1, 19), min(8, 18)):
        await page.goto(f"{BASE_URL}/product/{pid}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.4)


# Journey dispatcher
JOURNEY_MAP = {
    "browse_only": journey_browse_only,
    "full_purchase": journey_full_purchase,
    "search_browse": journey_search_browse,
    "trigger_errors": journey_trigger_errors,
    "rapid_clicks": journey_rapid_clicks,
    "abandon_cart": journey_abandon_cart,
    "quick_buy": journey_quick_buy,
    "admin_check": journey_admin_check,
    "compare_products": journey_compare_products,
    "search_edge_cases": journey_search_edge_cases,
    "multi_tab_browse": journey_multi_tab_browse,
}

# ─── Session Runner ──────────────────────────────────────────────────────────

async def run_persona(playwright, persona, headless=True, loop_count=0):
    """Run a single persona's session in a dedicated browser context."""
    iteration = 0
    browser = await playwright.chromium.launch(headless=headless)

    try:
        while loop_count == 0 or iteration < loop_count:
            iteration += 1
            context = await browser.new_context(
                viewport=persona["viewport"],
                user_agent=persona.get("user_agent"),
            )
            page = await context.new_page()

            # Set RUM user context via the page
            await page.add_init_script(f"""
                window.__DD_USER__ = {{
                    id: "{persona['email']}",
                    name: "{persona['name']}",
                    email: "{persona['email']}",
                    role: "{persona['role']}"
                }};
            """)

            # Pick a journey
            journey_name = persona["journeys"][iteration % len(persona["journeys"])]
            journey_fn = JOURNEY_MAP.get(journey_name, journey_browse_only)

            print(f"  [{ts()}] 🧑 {persona['name']:20s} | journey: {journey_name}")

            try:
                await journey_fn(page, persona)
            except Exception as e:
                print(f"  [{ts()}] ⚠️  {persona['name']:20s} | {journey_name} error: {type(e).__name__}: {str(e)[:80]}")

            await context.close()

            # Pause between sessions (simulate user leaving and coming back)
            pause = random.uniform(3, 8)
            await asyncio.sleep(pause)

    except asyncio.CancelledError:
        pass
    finally:
        await browser.close()


# ─── Main ────────────────────────────────────────────────────────────────────

async def main(num_users=3, headless=True, loops=0):
    print(f"\n{'='*60}")
    print(f"  🐕 Datadog RUM Load Generator")
    print(f"  Target:   {BASE_URL}")
    print(f"  Users:    {num_users} concurrent browsers")
    print(f"  Headless: {headless}")
    print(f"  Loops:    {'infinite' if loops == 0 else loops}")
    print(f"{'='*60}\n")

    # Also need to set the RUM user in the frontend
    # We inject it via page.add_init_script above, but the frontend
    # needs to pick it up — add a listener in the datadog init
    print("  ⚡ Tip: The frontend will auto-tag sessions with user data.\n")

    async with async_playwright() as pw:
        selected = random.sample(PERSONAS, min(num_users, len(PERSONAS)))
        if num_users > len(PERSONAS):
            # Duplicate personas for extra users
            while len(selected) < num_users:
                extra = random.choice(PERSONAS).copy()
                extra["name"] = f"{extra['name']} (clone-{len(selected)})"
                extra["email"] = f"clone{len(selected)}@demo.com"
                selected.append(extra)

        tasks = [
            asyncio.create_task(run_persona(pw, p, headless, loops))
            for p in selected
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RUM Load Generator")
    parser.add_argument("--users", type=int, default=3, help="Concurrent browser users (default: 3)")
    parser.add_argument("--headful", action="store_true", help="Show browser windows")
    parser.add_argument("--loops", type=int, default=0, help="Loops per user (0=infinite)")
    args = parser.parse_args()

    # Graceful shutdown
    loop = asyncio.new_event_loop()

    def shutdown(sig, frame):
        print(f"\n  🛑 Shutting down ({sig})...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, lambda s, f: shutdown(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: shutdown(s, f))

    try:
        loop.run_until_complete(main(args.users, not args.headful, args.loops))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("  ✅ All browsers closed.\n")
