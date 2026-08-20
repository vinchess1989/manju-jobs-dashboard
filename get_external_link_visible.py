import time
import sys
from playwright.sync_api import sync_playwright

def get_external_link(job_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=r'C:\Users\vinee\Manju_jobs_private\sessions\linkedin_session.json')
        page = context.new_page()
        page.set_default_navigation_timeout(60000)
        page.set_default_timeout(60000)
        page.goto(job_url)
        time.sleep(5)
        
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
            
            # Wait for user to see it
            time.sleep(2)
            
            with context.expect_page() as new_page_info:
                apply_btn.click(force=True)
            new_page = new_page_info.value
            new_page.wait_for_load_state()
            time.sleep(5)
            print("External URL:", new_page.url)
            
            # Save it so the agent can read it
            with open("external_url.txt", "w") as f:
                f.write(new_page.url)
        else:
            print("No Apply button found!")
        browser.close()

if __name__ == "__main__":
    get_external_link("https://fi.linkedin.com/jobs/view/content-editor-remote-at-yo-it-consulting-4423896008")
