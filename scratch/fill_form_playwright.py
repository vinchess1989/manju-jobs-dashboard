import sys
import time
import json
from playwright.sync_api import sync_playwright

url = "https://www.heikkilaco.fi/juristi-tyopaikka/#tyohakemus"
resume_path = r"C:\Users\vinee\Manju_jobs_private\Resumes\4427b75f\Manju_Krishna_juristi_Heikkil_Co_Oy_resume.pdf"
cover_letter_path = r"C:\Users\vinee\Manju_jobs_private\Resumes\4427b75f\Manju_Krishna_juristi_Heikkil_Co_Oy_cover_letter.pdf"

answers = [
  {"label": "Mitä työpaikkaa haet?", "type": "text", "answer": "Juristi"},
  {"label": "Etunimi", "type": "text", "answer": "Manju"},
  {"label": "Sukunimi", "type": "text", "answer": "Krishna Haridas"},
  {"label": "Syötä sähköpostiosoite", "type": "email", "answer": "munchnambiar@gmail.com"},
  {"label": "Vahvista sähköpostiosoite", "type": "email", "answer": "munchnambiar@gmail.com"},
  {"label": "Puhelinnumerosi", "type": "tel", "answer": "+358 415765217"},
  {"label": "Lähiosoite", "type": "text", "answer": "Tuirantie 13 A22"},
  {"label": "Kaupunki", "type": "text", "answer": "Oulu"},
  {"label": "Postinumero", "type": "text", "answer": "90500"},
  {"label": "Paras aika soittaa sinulle", "type": "select", "answer": "Iltapäivä"},
  {"label": "Hyväksyn henkilötietojeni käsittelyn siten kun se on määritelty tietosuojaselosteessa.", "type": "checkbox", "answer": "true"}
]

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Keep visible for user review
        page = browser.new_page()
        print("Navigating to URL...")
        page.goto(url)
        
        # Aggressively remove GDPR cookie banner to prevent it from blocking clicks
        try:
            page.evaluate('() => { const banner = document.getElementById("moove_gdpr_cookie_info_bar"); if (banner) banner.remove(); }')
        except Exception:
            pass

        print("Filling out text fields...")
        for item in answers:
            label = item["label"]
            ans = item["answer"]
            typ = item["type"]
            
            try:
                if typ in ["text", "email", "tel"]:
                    page.get_by_label(label, exact=False).first.fill(ans, timeout=5000)
                elif typ == "select":
                    # For dropdowns, try selecting by label first, if it fails, try by value
                    select_elem = page.get_by_label(label, exact=False).first
                    try:
                        select_elem.select_option(label=ans, timeout=3000)
                    except:
                        select_elem.select_option(value=ans, timeout=3000)
                elif typ == "checkbox" and ans == "true":
                    # Force click to bypass any remaining invisible overlays
                    page.get_by_label(label, exact=False).first.check(force=True, timeout=5000)
                print(f"Successfully filled: {label}")
            except Exception as e:
                print(f"Failed to fill {label}: {str(e)[:100]}...")

        # Handle file upload specifically
        try:
            print("Uploading files...")
            # We look for input type file
            file_input = page.locator("input[type='file']")
            file_input.set_input_files([resume_path, cover_letter_path])
            print("Successfully uploaded resume and cover letter.")
        except Exception as e:
            print(f"Failed to upload files: {e}")

        print("Form is filled! Browser will stay open for 60 seconds for you to review and submit.")
        time.sleep(60)
        browser.close()

if __name__ == "__main__":
    run()
