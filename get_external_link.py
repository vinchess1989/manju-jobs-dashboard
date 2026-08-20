import time
import sys
from playwright.sync_api import sync_playwright

def get_external_link(job_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=r'C:\Users\vinee\Manju_jobs_private\sessions\linkedin_session.json')
        page = context.new_page()
        page.set_default_navigation_timeout(60000)
        page.set_default_timeout(60000)
        page.goto(job_url)
        time.sleep(3)
        
        apply_btn = None
        for sel in ['button', 'a']:
            elements = page.query_selector_all(sel)
            for el in elements:
                try:
                    text = el.inner_text().strip()
                    if text == "Hae" or text == "Apply":
                        apply_btn = el
                        break
                except:
                    pass
            if apply_btn:
                break
                
        if apply_btn:
            print("Found Apply button:", apply_btn.inner_text())
            apply_btn.click(force=True)
            time.sleep(3)
            with open("temp_dom_after_click.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Dumped DOM to temp_dom_after_click.html")
        else:
            print("No Apply button found!")
        browser.close()

if __name__ == "__main__":
    get_external_link("https://fi.linkedin.com/jobs/view/content-editor-remote-at-yo-it-consulting-4423896008")
