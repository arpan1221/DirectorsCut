Monitor the running application for errors and auto-fix them.

Process:
1. Read the most recent server logs (check terminal output or log file)
2. Identify any errors, warnings, or exceptions
3. For each error:
   a. Classify: API error, type error, import error, runtime error
   b. Read the source file where the error occurred
   c. Read the relevant spec
   d. Apply fix
   e. Verify fix doesn't break tests: cd backend && python -m pytest tests/ -v
4. Report all fixes applied

If an error involves Gemini API rate limits or credit issues, DO NOT retry.
Report the issue and suggest a workaround (mock, cache, etc.)
