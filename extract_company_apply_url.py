import sys
import json
from playwright.sync_api import sync_playwright

def find_apply_url(job_url):
    apply_urls = []
    
    def handle_response(response):
        if "voyager" in response.url or "graphql" in response.url:
            try:
                text = response.text()
                if "companyApplyUrl" in text:
                    import re
                    matches = re.findall(r'"companyApplyUrl":"([^"]+)"', text)
                    if matches:
                        apply_urls.extend(matches)
            except:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=r"C:\Users\vinee\Manju_jobs_private\sessions\linkedin_session.json")
        page = context.new_page()
        page.on("response", handle_response)
        
        print("Navigating to:", job_url)
        page.goto(job_url, wait_until="networkidle")
        
        page.evaluate("window.scrollBy(0, 1000)")
        page.wait_for_timeout(3000)
        
        browser.close()
        
    return list(set(apply_urls))

if __name__ == "__main__":
    urls = find_apply_url("https://fi.linkedin.com/jobs/view/content-editor-remote-at-yo-it-consulting-4423896008")
    print("Extracted URLs:", urls)
