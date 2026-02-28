Run tests for: $ARGUMENTS (leave empty for all)

Process:
1. If empty: cd backend && python -m pytest tests/ -v --tb=short
2. If module specified: cd backend && python -m pytest tests/test_$ARGUMENTS.py -v --tb=short
3. For any failures:
   - Read the failing test and the implementation
   - Read the spec in docs/specs/
   - Fix the bug (in test or impl, whichever is wrong per spec)
   - Re-run
4. Report: pass/fail summary, any fixes applied
