import time
from playwright.sync_api import sync_playwright

def apply():
    url = "https://yohrconsultancy.hiresome.ai/apply_form/content-editor-remote-6a1e66a651f067635fb7e9e8?utm_source=linkedin"
    resume_path = r"C:\Users\vinee\Manju_jobs_private\Resumes\2d2757aa\Manju_Krishna_Content_Editor_Remote_YO_IT_Consulting_resume.pdf"
    
    with open("hiresome_script.log", "w") as log_file:
        def log(msg):
            print(msg)
            log_file.write(msg + "\n")
            log_file.flush()
            
        with sync_playwright() as p:
            log("Launching visible Chromium browser (slow_mo=50)...")
            browser = p.chromium.launch(headless=False, slow_mo=50)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_navigation_timeout(60000)
            page.set_default_timeout(60000)
            
            log(f"Navigating to {url}...")
            page.goto(url)
            page.wait_for_timeout(3000)
        
        # Upload Resume
            try:
                page.locator("input[type='file']").first.set_input_files(resume_path)
                log("Successfully uploaded resume!")
            except Exception as e:
                log("Failed to upload resume: " + str(e))
                
            # Give it a moment to parse if it does auto-parsing
            page.wait_for_timeout(5000)
            
            # Fill fields using JS injection to bypass visibility issues
            fields = {
                "name": "Manju Krishna Haridas",
                "email": "munchnambiar@gmail.com",
                "phone": "+358415765217",
                "preferredLocation": "Oulu, Finland / Remote",
                "currentDesignation": "Legal Editor & Associate",
                "currentCompany": "Poise Legal",
                "expectedCTC": "0",
                "totalExperience": "3",
                "highestDegree": "LL.M. Business and Corporate Law",
                "Keep an eye on your email Shortlisted candidates will receive nextstep instructions via email": "Understood"
            }
            
            for name, val in fields.items():
                try:
                    # Force fill to bypass visibility
                    page.locator(f"[name='{name}']").first.fill(val, force=True)
                    log(f"Filled {name}")
                except Exception as e:
                    # Fallback to JS injection
                    try:
                        js = f"""
                        let el = document.querySelector("[name='{name}']");
                        if (el) {{
                            el.value = "{val}";
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                        """
                        page.evaluate(js)
                        log(f"Injected {name}")
                    except Exception as e2:
                        log(f"Could not fill {name}")
                        
            # Notice Period dropdown is select
            try:
                page.locator("[name='noticePeriod']").first.select_option(label="<1 Month", force=True)
                log("Selected Notice Period")
            except:
                pass

            # Try to fill the react-select inputs for country, state, city
            try:
                # Country
                page.locator("#react-select-hs-ls-a-input").fill("Finland", force=True)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                # City
                page.locator("#react-select-hs-ls-c-input").fill("Oulu", force=True)
                page.keyboard.press("Enter")
                log("Filled Location dropdowns")
            except:
                log("Could not fill location dropdowns automatically")
                
            log("Done! Browser will stay open for 3 minutes for you to review and submit.")
            page.wait_for_timeout(180000)
            browser.close()

if __name__ == "__main__":
    apply()
