import time
import os
import hashlib
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def diagnose_site(name, url):
    print(f"\n=========================================")
    print(f"DIAGNOSING: {name} ({url})")
    print(f"=========================================")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a modern user agent to reduce bot-detection
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            print(f"Navigating to {url}...")
            response = page.goto(url, timeout=45000)
            print(f"Response status: {response.status if response else 'No response'}")
            print(f"Redirected/Final URL: {page.url}")
            
            # Wait for content to render
            time.sleep(5)
            
            # Scroll a bit
            for _ in range(2):
                page.mouse.wheel(0, 1000)
                time.sleep(1)
            
            # Capture screenshot
            screenshot_path = f"diagnose_{name}.png"
            page.screenshot(path=screenshot_path)
            print(f"Saved screenshot to {screenshot_path}")
            
            # Extract content
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Basic analysis
            title = page.title()
            print(f"Page Title: {title}")
            
            all_a = soup.find_all('a', href=True)
            print(f"Total <a> tags found: {len(all_a)}")
            
            # Check how many links match the current generic rules
            matching_links = []
            for a in all_a:
                href = a['href']
                text = a.text.strip()
                if any(kw in href.lower() for kw in ['/tyopaikka', '/job', '/view', '/rc/clk', '/avoimet-tyopaikat']):
                    matching_links.append((href, text))
            
            print(f"Links matching parser keywords: {len(matching_links)}")
            
            # Let's print first 20 links
            print("\nFirst 20 links found on page:")
            for i, a in enumerate(all_a[:20]):
                print(f"  [{i}] Href: {a['href']} | Text: {a.text.strip()[:50]}")
                
            # If we had matching links, print them
            if matching_links:
                print(f"\nMatching links (first 10):")
                for i, (href, text) in enumerate(matching_links[:10]):
                    print(f"  [{i}] Href: {href} | Text: {text[:50]}")
            
            # Specific heuristic check for SPAs or consent walls
            body_text = page.locator('body').inner_text()
            print(f"Body text length: {len(body_text)}")
            print(f"Preview of body text:\n{body_text[:500]}")
            
        except Exception as e:
            print(f"Error during diagnosis of {name}: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    targets = [
        ("duunitori", "https://duunitori.fi/tyopaikat?jarjestys=uusimmat"),
        ("meetfrank", "https://meetfrank.com/jobs/"),
        ("oikotie", "https://tyopaikat.oikotie.fi/tyopaikat?jarjestys=julkaisuaika"),
        ("hub_no", "https://hub.no/jobs")
    ]
    for name, url in targets:
        diagnose_site(name, url)
