import os
import sys

# Add current directory to path so we can import local modules
PUBLIC_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\manju-jobs-dashboard"
PRIVATE_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\Manju-jobs"
PHOTO_PATH = os.path.join(PRIVATE_DIR, "manju_photo.JPG")
OUT_DIR = os.path.join(PRIVATE_DIR, "Resumes")

if PUBLIC_DIR not in sys.path:
    sys.path.insert(0, PUBLIC_DIR)

import make_resume
import html_to_pdf

# Get jobs from command line arguments if provided, otherwise default to current batch
if len(sys.argv) > 1:
    jobs_to_process = sys.argv[1:]
else:
    jobs_to_process = ["014367c5", "f96f492b", "0f7d4796", "e570a5a7", "c430b454"]

print("Starting batch resume and cover letter generation...")
print(f"Jobs: {', '.join(jobs_to_process)}")

for job_id in jobs_to_process:
    print(f"\n----------------------------------------")
    print(f"Processing Job ID: {job_id}")
    
    json_path = os.path.join(OUT_DIR, job_id, f"{job_id}_data.json")
    if not os.path.exists(json_path):
        print(f"ERROR: JSON data file not found: {json_path}")
        continue
        
    try:
        # 1. Generate HTML files
        print(f"Generating HTML documents...")
        resume_html, cl_html = make_resume.generate(json_path, PHOTO_PATH, OUT_DIR)
        
        # 2. Convert to PDF using Playwright
        print(f"Converting HTML to PDF via Playwright...")
        html_to_pdf.html_to_pdf(resume_html)
        html_to_pdf.html_to_pdf(cl_html)
        
        print(f"Successfully processed Job ID: {job_id}")
    except Exception as e:
        print(f"ERROR processing Job ID {job_id}: {e}")
        import traceback
        traceback.print_exc()

print("\n----------------------------------------")
print("Batch processing completed.")
