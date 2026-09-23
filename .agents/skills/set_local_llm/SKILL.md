---
name: set_local_llm
description: Updates the system's local LLM configuration. Since scrapers automatically pick the loaded model, this skill is now a no-op placeholder that documents the current behavior.
---

# set_local_llm

**Purpose**: Ensure the environment reflects the currently loaded LLM model for downstream scrapers.

## Current Behavior
- Scrapers automatically detect and use the model loaded in LM Studio.
- No manual model switch is required.

## Implementation
- This skill records the model name in `config/local_model.txt` for reference (optional).
- If the file already exists, it overwrites it with the current model identifier.
- The actual model selection is handled by LM Studio; the skill does not invoke any external commands.

## Steps
1. **Read current model**: The model name can be obtained from the environment variable `LM_STUDIO_MODEL` or a similar config.
2. **Write to reference file**:
   ```powershell
   powershell -ExecutionPolicy Bypass -Command "& 'python' -c \"import os; open('config/local_model.txt','w').write(os.getenv('LM_STUDIO_MODEL','unknown'))\""
   ```
   (Wrapped in PowerShell per global rules.)
3. **Output**: Log a message indicating the model has been recorded.

> **Note**: This skill exists primarily for documentation and future extensibility; the scrapers will continue to function without it.
