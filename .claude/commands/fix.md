An error has occurred: $ARGUMENTS

Process:
1. Read the full error/traceback
2. Identify the exact file and line
3. Read that file and the relevant spec in docs/specs/
4. Determine root cause (type error, logic error, import error, API error, missing dep)
5. Apply the minimal fix that aligns with the spec
6. Run: cd backend && python -m pytest tests/ -v --tb=short
7. If new failures appear, fix those too (max 3 cycles)
8. Report: what was wrong, what you fixed, test results

Rules:
- Do NOT change models.py unless the spec requires it
- Do NOT add new pip dependencies without flagging it
- Do NOT make real Gemini API calls — use mocks in tests
