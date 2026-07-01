#!/usr/bin/env python3
"""
Generate 1-page A4 HTML resume AND cover letter from a single job data JSON.

Usage:
    python make_resume.py <JOBID_data.json> --photo <path/to/photo.jpg> --out-dir <Resumes/>

Output (inside out-dir/<job_id>/):
    Manju_Krishna_<JobTitle>_<Company>_resume.html
    Manju_Krishna_<JobTitle>_<Company>_cover_letter.html

Then convert to PDF:
    python html_to_pdf.py <resume.html> <cover_letter.html>

Data JSON structure:
{
  "job_id": "f6aaa66f",
  "job_title": "Legal Trainee",
  "company": "Hiab",
  "resume": {
    "name": "Manju Krishna Haridas",
    "role": "Legal Trainee Candidate",
    "contact": { "address": "...", "phone": "...", "email": "...",
                 "linkedin_url": "...", "linkedin_display": "..." },
    "profile": "...",
    "experience": [
      { "title": "...", "company": "...", "dates": "...", "bullets": ["..."] }
    ],
    "education": [
      { "qual": "...", "inst": "...", "bold": false }
    ],
    "languages_html": "...",
    "competencies_html": "...",
    "references": [
      { "name": "...", "title": "...", "contact": "..." }
    ]
  },
  "cover_letter": {
    "date": "23 June 2026",
    "recipient": { "title": "Hiring Manager", "team": "...", "company": "...", "city": "..." },
    "paragraphs": ["...", "..."],
    "sign_off": "Yours sincerely"
  }
}
"""

import json
import base64
import sys
import os
import re
import argparse
from pathlib import Path

DEFAULT_PHOTO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "Manju-jobs", "manju_photo.JPG"
)

# ── RESUME TEMPLATE ──────────────────────────────────────────────────────────

RESUME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{name} — CV</title>
<style>
@page {{ size: A4; margin: 11mm 13mm 10mm 13mm; }}
@media print {{
  body {{ margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Calibri', 'Segoe UI', Arial, sans-serif;
  font-size: 9.2pt; line-height: 1.35; color: #1e1e1e;
  background: #fff; width: 184mm; margin: 0 auto;
}}
.header {{
  display: flex; align-items: flex-start; gap: 14px;
  padding-bottom: 7px; border-bottom: 2.5px solid #1a4f82; margin-bottom: 7px;
}}
.photo {{
  width: 74px; height: 93px; object-fit: cover;
  object-position: top center; border-radius: 3px;
  flex-shrink: 0; border: 1px solid #ccc;
}}
.header-text {{ flex: 1; }}
.header-text h1 {{
  font-size: 17.5pt; font-weight: 800; color: #0e2d50;
  letter-spacing: 0.4px; line-height: 1;
}}
.header-text .role {{
  font-size: 10pt; color: #1a4f82; font-weight: 600; margin: 3px 0 6px;
}}
.header-text .contact {{ font-size: 8.3pt; color: #444; line-height: 1.65; }}
.header-text .contact a {{ color: #1a4f82; text-decoration: none; }}
h2 {{
  font-size: 8.8pt; font-weight: 800; color: #1a4f82;
  text-transform: uppercase; letter-spacing: 0.9px;
  border-bottom: 1px solid #1a4f82; padding-bottom: 1.5px; margin: 7px 0 4px;
}}
.profile-text {{ font-size: 8.8pt; line-height: 1.42; color: #2a2a2a; }}
.job {{ margin-bottom: 5px; }}
.job-header {{ display: flex; justify-content: space-between; align-items: baseline; }}
.job-title {{ font-weight: 700; font-size: 9.2pt; }}
.job-co {{ font-style: italic; color: #444; font-size: 8.8pt; }}
.job-date {{ font-size: 8.2pt; color: #666; white-space: nowrap; padding-left: 6px; }}
ul {{ padding-left: 13px; margin-top: 2px; }}
li {{ font-size: 8.5pt; line-height: 1.38; margin-bottom: 1px; }}
.two-col {{ display: flex; gap: 14px; margin-top: 1px; }}
.col-left {{ flex: 0 0 50%; }}
.col-right {{ flex: 1; }}
.edu-table {{ width: 100%; border-collapse: collapse; }}
.edu-table tr {{ vertical-align: top; }}
.edu-table td {{ font-size: 8.3pt; line-height: 1.35; padding: 1.5px 2px; }}
.edu-table .qual {{ font-weight: 600; }}
.edu-table .inst {{ color: #555; text-align: right; white-space: nowrap; padding-left: 4px; }}
.highlight {{ color: #0e2d50; }}
.skill-block {{ font-size: 8.5pt; line-height: 1.55; }}
.skill-cat {{ font-weight: 700; color: #1a4f82; }}
.ref {{ font-size: 8.3pt; line-height: 1.4; margin-bottom: 4px; }}
.ref-name {{ font-weight: 700; }}
</style>
</head>
<body>

<div class="header">
  <img class="photo" src="data:image/jpeg;base64,{photo_b64}" alt="{name}">
  <div class="header-text">
    <h1>{name_upper}</h1>
    <div class="role">{role}</div>
    <div class="contact">
      {address}<br>
      {phone} &nbsp;|&nbsp; <a href="mailto:{email}">{email}</a> &nbsp;|&nbsp;
      <a href="{linkedin_url}">{linkedin_display}</a>
    </div>
  </div>
</div>

<h2>Professional Profile</h2>
<div class="profile-text">{profile}</div>

<h2>Professional Experience</h2>
{experience_html}

<div class="two-col">
<div class="col-left">
<h2>Education</h2>
<table class="edu-table">
{education_html}
</table>
<h2>Languages &amp; Skills</h2>
<div class="skill-block">{languages_html}</div>
<h2>References</h2>
{references_html}
</div>
<div class="col-right">
<h2>Core Legal Competencies</h2>
<div class="skill-block">{competencies_html}</div>
</div>
</div>

</body>
</html>"""

# ── COVER LETTER TEMPLATE ─────────────────────────────────────────────────────

COVER_LETTER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{name} — Cover Letter</title>
<style>
@page {{ size: A4; margin: 20mm 22mm 18mm 22mm; }}
@media print {{
  body {{ margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Calibri', 'Segoe UI', Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.5; color: #1e1e1e;
  background: #fff; width: 166mm; margin: 0 auto;
}}
.sender {{
  font-size: 10pt; color: #1a4f82; font-weight: 600;
  border-bottom: 2px solid #1a4f82; padding-bottom: 6px; margin-bottom: 16px;
}}
.sender .name {{ font-size: 14pt; font-weight: 800; color: #0e2d50; }}
.sender .contact {{ font-size: 9pt; color: #444; margin-top: 3px; }}
.sender .contact a {{ color: #1a4f82; text-decoration: none; }}
.date {{ font-size: 10pt; color: #444; margin-bottom: 14px; }}
.recipient {{ font-size: 10pt; margin-bottom: 14px; line-height: 1.6; }}
.salutation {{ margin-bottom: 12px; font-weight: 600; }}
.body p {{ margin-bottom: 10px; text-align: justify; }}
.sign-off {{ margin-top: 20px; }}
.sign-name {{ font-weight: 800; font-size: 11pt; color: #0e2d50; margin-top: 6px; }}
</style>
</head>
<body>

<div class="sender">
  <div class="name">{name}</div>
  <div class="contact">
    {address} &nbsp;|&nbsp; {phone}<br>
    <a href="mailto:{email}">{email}</a> &nbsp;|&nbsp;
    <a href="{linkedin_url}">{linkedin_display}</a>
  </div>
</div>

<div class="date">{date}</div>

<div class="recipient">
  {recipient_title}<br>
  {recipient_team}<br>
  {recipient_company}, {recipient_city}
</div>

<div class="salutation">Dear {recipient_title},</div>

<div class="body">
{paragraphs_html}
</div>

<div class="sign-off">
  {sign_off},<br>
  <div class="sign-name">{name}</div>
</div>

</body>
</html>"""


def slugify(text):
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")


def photo_to_b64(photo_path):
    with open(photo_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def render_experience(jobs):
    parts = []
    for j in jobs:
        bullets = "\n".join(f"      <li>{b}</li>" for b in j.get("bullets", []))
        parts.append(
            f'  <div class="job">\n'
            f'    <div class="job-header">\n'
            f'      <span class="job-title">{j.get("title", "")}</span>\n'
            f'      <span class="job-date">{j.get("dates", "")}</span>\n'
            f'    </div>\n'
            f'    <div class="job-co">{j.get("company", "")}</div>\n'
            f'    <ul>\n{bullets}\n    </ul>\n'
            f'  </div>'
        )
    return "\n".join(parts)


def render_education(rows):
    parts = []
    for r in rows:
        q = f"<strong>{r.get('qual', '')}</strong>" if r.get("bold") else r.get("qual", "")
        parts.append(
            f'  <tr><td class="qual">{q}</td>'
            f'<td class="inst">{r.get("inst", "")}</td></tr>'
        )
    return "\n".join(parts)


def render_references(refs):
    return "\n".join(
        f'  <div class="ref"><div class="ref-name">{r.get("name", "")}</div>'
        f'{r.get("title", "")}<br>{r.get("contact", "")}</div>'
        for r in refs
    )


def render_paragraphs(paras):
    return "\n".join(f"  <p>{p}</p>" for p in paras)


def generate(data_path, photo_path, out_dir):
    with open(data_path, encoding="utf-8") as f:
        d = json.load(f)

    job_id = d.get("job_id", "unknown_job")
    job_title = d.get("job_title", "Unknown Role")
    company = d.get("company", "Unknown Company")
    r = d.get("resume", {})
    cl = d.get("cover_letter", {})

    b64 = photo_to_b64(photo_path)

    # ── File naming ───────────────────────────────────────────────────────────
    slug = f"Manju_Krishna_{slugify(job_title)}_{slugify(company)}"
    folder = os.path.join(out_dir, job_id)
    os.makedirs(folder, exist_ok=True)

    # ── Resume HTML ───────────────────────────────────────────────────────────
    rc = r.get("contact", {})
    resume_html = RESUME_HTML.format(
        name=r.get("name", "Manju Krishna Haridas"),
        name_upper=r.get("name", "Manju Krishna Haridas").upper(),
        role=r.get("role", ""),
        address=rc.get("address", ""),
        phone=rc.get("phone", ""),
        email=rc.get("email", ""),
        linkedin_url=rc.get("linkedin_url", ""),
        linkedin_display=rc.get("linkedin_display", ""),
        profile=r.get("profile", ""),
        experience_html=render_experience(r.get("experience", [])),
        education_html=render_education(r.get("education", [])),
        languages_html=r.get("languages_html", ""),
        competencies_html=r.get("competencies_html", ""),
        references_html=render_references(r.get("references", [])),
        photo_b64=b64,
    )
    resume_out = os.path.join(folder, f"{slug}_resume.html")
    with open(resume_out, "w", encoding="utf-8") as f:
        f.write(resume_html)
    print(f"  Resume HTML : {resume_out}")

    # ── Cover letter HTML ─────────────────────────────────────────────────────
    rec = cl.get("recipient", {})
    cl_html = COVER_LETTER_HTML.format(
        name=r.get("name", "Manju Krishna Haridas"),
        address=rc.get("address", ""),
        phone=rc.get("phone", ""),
        email=rc.get("email", ""),
        linkedin_url=rc.get("linkedin_url", ""),
        linkedin_display=rc.get("linkedin_display", ""),
        date=cl.get("date", ""),
        recipient_title=rec.get("title", ""),
        recipient_team=rec.get("team", ""),
        recipient_company=rec.get("company", ""),
        recipient_city=rec.get("city", ""),
        paragraphs_html=render_paragraphs(cl.get("paragraphs", [])),
        sign_off=cl.get("sign_off", "Yours sincerely"),
    )
    cl_out = os.path.join(folder, f"{slug}_cover_letter.html")
    with open(cl_out, "w", encoding="utf-8") as f:
        f.write(cl_html)
    print(f"  Letter HTML : {cl_out}")

    return resume_out, cl_out


def main():
    parser = argparse.ArgumentParser(
        description="Generate resume + cover letter HTML from a job data JSON."
    )
    parser.add_argument("data", help="Path to JOBID_data.json")
    parser.add_argument(
        "--photo",
        default=DEFAULT_PHOTO,
        help="Path to candidate photo (JPEG). Default: ../Manju-jobs/manju_photo.JPG",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Base output directory (Resumes/ folder). Defaults to sibling ../Manju-jobs/Resumes/",
    )
    args = parser.parse_args()

    out_dir = args.out_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "Manju-jobs", "Resumes"
    )

    print(f"Generating documents for: {args.data}")
    generate(args.data, args.photo, out_dir)
    print("Done. Run html_to_pdf.py on the HTML files to produce PDFs.")


if __name__ == "__main__":
    main()
