Implement the module described in the spec file at: docs/specs/$ARGUMENTS

Process:
1. Read the spec file completely
2. Read backend/app/models.py for all Pydantic types
3. Read CLAUDE.md for conventions and constraints
4. Implement in the appropriate file under backend/app/
5. Write matching tests in backend/tests/ — ALL Gemini calls must be mocked
6. Run: cd backend && python -m pytest tests/ -v --tb=short
7. If tests fail, fix and re-run (max 3 retries)
8. Report: what was implemented, what tests pass, any issues
