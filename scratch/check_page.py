import os
import sys
import time
from playwright.sync_api import sync_playwright

# Reconfigure stdout to use UTF-8 to prevent charmap encoding errors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

url = "https://fi.indeed.com/rc/clk?jk=1c8b70d61c02a10a&bb=jmSsORmAmG0pDucXnsF7XtiEJbRvZ0D18zxjCxtw8MahmpkB4kx-kl8cKi_88-c13183ippbUFVR7e2bW02kYAN6B17dkNnIQEZkm8kCr9yFvJETZFQ5rEWn4DlBombg&xkcb=SoDf67M3ioRMhiTBMx0PbzkdCdPP&fccid=592bbc8c0a772dc4&vjs=3"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # Evade webdriver detection
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    page = context.new_page()
    try:
        print("Navigating...")
        page.goto(url, timeout=30000)
        time.sleep(3) # wait for render
        text = page.locator('body').inner_text()
        print("Length of text:", len(text))
        print("First 1000 chars of text:")
        print(text[:1000])
        print("\nSearching for potential location terms (e.g. Helsinki, Espoo, Vantaa, Tampere, Turku, Finland, Oulu, Suomi):")
        for word in ["Helsinki", "Espoo", "Vantaa", "Tampere", "Turku", "Finland", "Oulu", "Suomi", "Kouvola", "Lahti", "Kuopio", "Jyväskylä"]:
            if word.lower() in text.lower():
                print(f"Found word: {word}")
        # Save full text to a scratch file
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/indeed_page.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print("Saved full text to scratch/indeed_page.txt")
    except Exception as e:
        print("Error:", e)
    finally:
        browser.close()

