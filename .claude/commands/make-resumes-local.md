Run the full local LLM resume generation pipeline for a given set of job IDs.
This skill will tailor the resume JSON via LM Studio, build the HTML/PDF resumes, commit them to the private repository, sync the links to Firestore, and commit the public repository updates.

## Steps

### 1. Run the local LLM pipeline script
```powershell
cd c:\Users\vinee\manju_jobs
.\run_local_llm_pipeline.ps1 <JOB_ID_1> <JOB_ID_2>
```

Replace `<JOB_ID_X>` with the IDs of the jobs you want to generate resumes for (e.g. `.\run_local_llm_pipeline.ps1 a868c0e7`). You can pass multiple IDs separated by spaces.

### 2. Verify Output
Report whether the script succeeded, what PDFs were generated, and whether the git pushes and Firestore sync completed successfully.
