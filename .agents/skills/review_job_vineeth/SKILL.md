---
name: review-job-vineeth
description: Reviews job URLs to check if they are still accepting applications. If they are closed, moves them to deleted.json.
---

When invoked with `review-job <job_id> <job_id> ...`, your task is to verify if the given jobs are still accepting applications.

Follow these steps for EACH `job_id`:
1. Use the `run_command` tool to extract the URL for the `job_id` from `jobs.json` or `deleted.json` (for verification). A quick way is:
   `python -c "import json; print([j['url'] for j in json.load(open('jobs.json', encoding='utf-8')) if j['id'] == '<job_id>'])"`
2. Use the `read_url_content` tool to fetch the webpage of that URL.
3. Check the returned markdown content. The job is CLOSED if you find any of these phrases (case-insensitive):
   - "No longer accepting applications"
   - "Työpaikkailmoitus on arkistoitu"
   - "hakuaika on päättynyt"
   - "Työpaikkailmoitus on poistunut"
   - "Työpaikkailmoitus on piilotettu"
4. If the job is CLOSED:
   - Run the helper script to move it to `deleted.json`:
     `venv\Scripts\python.exe scratch\move_to_deleted.py <job_id> "Closed: No longer accepting applications"`
   - Output to the user that the job was closed and moved to `deleted.json`.
5. If the job is still OPEN (none of the phrases are found):
   - Output to the user that the job is still active and can be processed.

If multiple `job_id`s are provided, process all of them sequentially.
