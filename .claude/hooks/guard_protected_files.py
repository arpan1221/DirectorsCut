#!/usr/bin/env python3
"""
PreToolUse hook: blocks edits to models.py and .env files.
models.py is locked per CLAUDE.md: "do not change without asking"
.env files must never be committed or modified by Claude.
"""
import sys
import json

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")

if "models.py" in path:
    print("BLOCKED: models.py is locked per CLAUDE.md rule #4.")
    print("All Pydantic types are already written. Ask the user before changing this file.")
    sys.exit(2)

if ".env" in path and not path.endswith(".env.example"):
    print("BLOCKED: Never edit .env files. Set env vars manually.")
    sys.exit(2)
