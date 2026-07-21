# Powershell Execution Rule
- Wrap all commands you run for the user in PowerShell (e.g. `powershell -Command "..."`).

## Database Modifications and Race Conditions
If we ever need to do bulk manual database modifications via scripts (e.g., editing jobs.json or curated_jobs.json), we must:
1. Temporarily stop the orchestrator.py script.
2. Apply the JSON edits.
3. Wipe any conflicting states from Firebase's shared_state and user_feedback caches.
4. Restart the scraper/orchestrator.
This is to prevent the background scraper from overriding manual JSON edits with stale state from Firebase or its in-memory cache.
