@echo off
set "TASK_NAME=ManjuJobsLocalLLMOrchestrator"
set "PYTHON_EXE=C:\Users\vinee\manju_jobs\venv\Scripts\python.exe"
set "SCRIPT_PATH=C:\Users\vinee\manju_jobs\orchestrator.py"
set "START_DIR=C:\Users\vinee\manju_jobs"
set "SCHEDULE_TIME=08:00"

echo ========================================================
echo Setting up Windows Scheduled Task for Local LLM Pipeline
echo ========================================================

schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" /sc daily /st 00:00 /ri 360 /du 24:00 /f

echo.
echo The task "%TASK_NAME%" has been scheduled to run 4 times a day (every 6 hours starting at 00:00).
echo It will run completely silently in the background, utilizing your local LLM.
echo.
