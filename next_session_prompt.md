# Resume Generation Workflow — Next Session Prompt

### Primary Orchestrator Agent Session
- **Conversation ID:** `062adaef-2845-407e-958e-be22ad8a52ee`
- **Purpose:** This session holds the background tasks (cron jobs) that monitor `orchestrator.log` for broken search sites and dynamically evaluate the local LLM outputs. 
- **To Resume/Manage:** If you need to kill or check the status of those background tasks, paste this Conversation ID into *any* chat and tell the agent: "Check the background tasks for conversation 062adaef-2845-407e-958e-be22ad8a52ee using the manage_task tool."

## Repo locations
- PUBLIC:  `c:\Users\vinee\manju_jobs`           (vinchess1989/manju-jobs-dashboard)
- PRIVATE: `c:\Users\vinee\Manju_jobs_private`   (munchnambiar/Manju-jobs)

## Scripts (all in PUBLIC repo root)
- `find_matching_jobs.py`  — filters jobs.json; use `--or` for OR logic
- `make_resume.py`         — takes `<job_id>_data.json` → outputs HTML resume + cover letter into `Resumes/<job_id>/` in PRIVATE repo
- `html_to_pdf.py`         — converts HTML → PDF via Playwright
- `upload_resume_links.py` — writes resume_url / cover_letter_url to Firestore

## Candidate photo
`c:\Users\vinee\Manju_jobs_private\manju_photo.JPG`
(make_resume.py already defaults to this path)

## Firestore
Project: manju-jobs-dashboard
Collection: shared_state / doc: job_status
Keys: job URL → { resume_url, cover_letter_url, applied, user_review }
No auth needed (rules: allow update: if true)

## Job descriptions
Scraper saves full text to `job_descriptions/<filename>.txt` in public repo.
Access via GitHub Pages: `https://vinchess1989.github.io/manju-jobs-dashboard/job_descriptions/<filename>.txt`
filename is in jobs.json field: `description_file` (strip the `job_descriptions/` prefix)

## Manju's profile summary
- LL.M. Business & Corporate Law, First Rank — Symbiosis International University (2020–21)
- LL.B. First Class Honours, Top 3 — University of Calicut (2009–14)
- Finnish Supplementary Law Studies (OPH bar path) — University of Lapland (2025–present)
- Kohti Yliopistoa — University of Oulu (2025–26)
- Law firm placement: Regelin Oy, Oulu (Apr–Jun 2026) — Finnish legal practice
- International House Oulu intern — event coordination, OuluBot
- Legal Associate: Poise Legal India (Oct 2021–May 2022) — 5–7 contracts/month
- Junior Lawyer: Juris Nexus India (Sep 2015–Jan 2016)
- English C1, Finnish B2, Malayalam native. Based in Oulu. Available Sep 2026.

## Completed so far
- Hiab Legal Trainee (`f6aaa66f`): PDF resume + cover letter done, in `Resumes/f6aaa66f/`
- OP Jokilaaksot Juristi (`f062b3e0`): PDF resume + cover letter done, Firestore updated, in `Resumes/f062b3e0/`

## Known issues with description files
Many scraped job descriptions are just Cloudflare/LinkedIn login-wall boilerplate — no real content.

**Fallback process when description file has no content:**
1. Check the description file has real content (>200 meaningful words after the JOB DESCRIPTION header).
2. If not, use WebFetch on the job's actual URL (`url` field in jobs.json / `job_link` in filtered JSON).
3. If that is also blocked, try the company's careers page or a web search for the job title + company.
4. Only skip a job if all three methods yield no usable description.

Jobs with real descriptions found so far: f062b3e0 (OP Pohjola), 0f7d4796 (Kela), 425e1772 (SATA Shipbuilding).
Jobs without (description file blocked): de8e59b8 (Indeed), e570a5a7 (LinkedIn).

## Task

1. Pull latest from both repos:
   ```
   git -C "c:\Users\vinee\manju_jobs" pull
   git -C "c:\Users\vinee\Manju_jobs_private" pull
   ```

2. Run find_matching_jobs.py to get the current list of jobs needing resumes:
   ```
   cd "c:\Users\vinee\manju_jobs"
   python find_matching_jobs.py --posted-days 3 --deadline-days 3 --or posted-days deadline-days
   ```
   (This produces a timestamped `jobs_<ts>.json` — read that file)

3. From the output, identify jobs where `matches_requirements == "yes"` and
   no `Resumes/<job_id>/` folder exists yet in the private repo (i.e. not yet processed).
   Skip `f6aaa66f` (Hiab — already done).

4. For each unprocessed job (work in batches of 5):

   a. Fetch the job description from GitHub Pages using the `description_file` field.

   b. Write a tailored `Resumes/<job_id>/<job_id>_data.json` in the PRIVATE repo.
      Use `Resumes/f6aaa66f/f6aaa66f_data.json` as the structural template.
      Tailor: profile paragraph, bullet points emphasis. Keep all 4 experience entries.
      Include the full `cover_letter` section with paragraphs addressing that specific role.

   c. Run from the PUBLIC repo directory:
      ```
      python make_resume.py "..\Manju_jobs_private\Resumes\<job_id>\<job_id>_data.json" --photo "..\Manju_jobs_private\manju_photo.JPG" --out-dir "..\Manju_jobs_private\Resumes"
      ```
      (Both --photo and --out-dir are required — defaults point to old ../Manju-jobs/ path)

   d. Run:
      ```
      python html_to_pdf.py "..\Manju_jobs_private\Resumes\<job_id>\Manju_Krishna_<Title>_<Company>_resume.html"
      python html_to_pdf.py "..\Manju_jobs_private\Resumes\<job_id>\Manju_Krishna_<Title>_<Company>_cover_letter.html"
      ```

   e. Push private repo after each batch:
      ```
      git -C "c:\Users\vinee\Manju_jobs_private" add Resumes/
      git -C "c:\Users\vinee\Manju_jobs_private" commit -m "Add resume docs for batch <n>"
      git -C "c:\Users\vinee\Manju_jobs_private" push
      ```

5. After all batches, update Firestore:
   - Edit/create `input.csv` in PUBLIC repo with rows:
     ```
     job_id,resume_url,cover_letter_url
     <job_id>,https://github.com/munchnambiar/Manju-jobs/blob/main/Resumes/<job_id>/Manju_Krishna_<Title>_<Company>_resume.pdf,https://github.com/munchnambiar/Manju-jobs/blob/main/Resumes/<job_id>/Manju_Krishna_<Title>_<Company>_cover_letter.pdf
     ```
   - Run:
     ```
     python upload_resume_links.py --input input.csv
     ```

6. Push public repo if any files changed (jobs.json, input.csv, etc.).
   Firebase deploy only if dashboard HTML was changed.

## Output naming convention
```
Resumes/<job_id>/Manju_Krishna_<JobTitle>_<Company>_resume.pdf
Resumes/<job_id>/Manju_Krishna_<JobTitle>_<Company>_cover_letter.pdf
```
(make_resume.py handles this automatically from `job_title` and `company` fields in the JSON)

---

**Start:** Pull both repos → run find_matching_jobs.py → list unprocessed "yes" jobs → show the list before generating any files. To test the workflow, tailor docs for only one job first.
