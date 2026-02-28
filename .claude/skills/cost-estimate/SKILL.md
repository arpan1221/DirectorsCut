---
name: cost-estimate
description: "Scans recent git diff for Gemini API calls and estimates cost against the $25 hackathon budget."
user-invocable: true
---

Scan `git diff HEAD` (or `git diff --staged` if nothing is unstaged) for Gemini model calls in backend/app/.

## Rates (from CLAUDE.md)
| Model | Cost/call |
|---|---|
| gemini-3-flash (emotion) | $0.0003 |
| gemini-3-pro-preview (director) | $0.005 |
| gemini-2.5-flash-image (scene image) | $0.039 |
| gemini-2.5-flash-preview-tts (narration) | $0.002 |

## Per full demo run (baseline)
- ~22 emotion calls (one every 8s over ~3min)
- ~3 director calls (one per decision point)
- ~3 image generation calls
- ~3 TTS calls

## Instructions
1. Run: `git diff HEAD -- backend/app/` to see changed files
2. For each changed file, count new or modified Gemini model invocations
3. Identify the model name from the `model=` argument or constant
4. Flag ANY call using a model not in the approved list above (especially 'nano-banana-pro' which is BANNED)
5. Multiply per-call costs by baseline call counts to estimate incremental cost per run
6. Output:
   - Table: model | calls/run | cost/run
   - **Estimated cost per full demo run**
   - **Remaining budget** (assume $25 total, ask user how much has been spent if unknown)
   - Any banned models found (hard stop — must be fixed before /commit)
