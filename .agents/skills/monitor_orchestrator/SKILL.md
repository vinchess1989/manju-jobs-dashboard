---
name: monitor_orchestrator
description: Monitors orchestrator.log, updates status, and patches broken code.
---

# monitor_orchestrator

**Prerequisite**: Run this ONLY if the orchestrator process is currently running.

1. **Check**: Read `orchestrator.log` for errors/tracebacks.
2. **Error**: Run `venv\Scripts\python.exe scratch\update_status.py error '<msg>'` and patch the bug.
3. **Success**: Run `venv\Scripts\python.exe scratch\update_status.py ok`.
*(Remember to use the PowerShell wrapper per global rules)*
