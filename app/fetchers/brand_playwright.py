"""
Brand-site Playwright fetcher (scaffold).

Once you add a specific hotel's booking URL and CSS selectors for the final price,
this will return a 'total with taxes' integer. Until then, it returns None so the
pipeline falls back to SerpAPI.

NOTE: Scraping brand sites may be restricted by Terms of Service. Use official APIs
or partner access when possible for production.
"""
from __future__ import annotations
import asyncio
from datetime import date, timedelta

try:
    # import lazily so Streamlit doesn't need Playwright at runtime
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover
    async_playwright = None  # type: ignore

def nightly_from_total(total: int, nights: int) -> int:
    return round(total / max(1, nights))

async def _fetch_total_example(hotel_url: str, checkin: date, nights: int, adults: int) -> int | None:
    """
    TEMPLATE for a brand site. Replace selectors with the site's DOM.
    """
    if async_playwright is None:
        return None

    checkout = checkin + timedelta(days=nights)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(locale="en-US")
        page = await ctx.new_page()

        # 1) open search page
        await page.goto(hotel_url, wait_until="networkidle")

        # 2) TODO: fill check-in, checkout, guests; submit (selectors differ per brand)
        # await page.fill("css=[data-test=checkin]", checkin.strftime("%Y-%m-%d"))
        # await page.fill("css=[data-test=checkout]", checkout.strftime("%Y-%m-%d"))
        # await page.click("css=[data-test=guests]")
        # await page.click("css=[data-test=search]")

        # 3) TODO: wait for results and extract total price *with taxes*
        # await page.wait_for_selector("css=.total-price")
        # price_text = await page.text_content("css=.total-price")

        await browser.close()
        return None  # until selectors are provided

def fetch_brand_total(hotel_url: str, checkin: date, nights: int = 1, adults: int = 2) -> int | None:
    """
    Synchronous wrapper for GitHub Actions convenience.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(
            _fetch_total_example(hotel_url, checkin, nights, adults)
        )
    except RuntimeError:
        # if no running loop
        return asyncio.run(_fetch_total_example(hotel_url, checkin, nights, adults))
