from playwright.sync_api import sync_playwright

url = "https://www.linkedin.com/jobs/view/legal-research-analyst-remote-at-crossing-hurdles-4427276865"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = context.new_page()
    page.goto(url, timeout=30000)
    
    text = page.locator('body').inner_text()
    
    # Just print the first 1000 characters which usually contain the header
    print(text[:1000])
    
    browser.close()
