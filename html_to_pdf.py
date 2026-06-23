"""Convert an HTML resume to a single A4 PDF using Playwright (headless Chromium)."""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright


async def html_to_pdf(html_path: str, out_path: str | None = None) -> str:
    src = Path(html_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)

    dest = Path(out_path) if out_path else src.with_suffix(".pdf")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(src.as_uri(), wait_until="networkidle")
        await page.pdf(
            path=str(dest),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,   # honours @page { size: A4 } in the HTML
        )
        await browser.close()

    print(f"PDF saved: {dest}")
    return str(dest)


if __name__ == "__main__":
    html_file = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\vinee\Manju_jobs_private\Resumes\f6aaa66f_resume.html"
    out_file  = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(html_to_pdf(html_file, out_file))
