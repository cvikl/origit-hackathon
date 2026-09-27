#!/usr/bin/env python3
"""Re-parse cached Bob evidence from the stored raw answer (no Bob call): python scripts/reparse-evidence.py <state-or-seed dir>"""
import glob, json, sys
from app import bobshell as B
n = 0
for f in glob.glob(sys.argv[1] + "/**/evidence/*.json", recursive=True) + glob.glob(sys.argv[1] + "/evidence/**/*.json", recursive=True):
    e = json.load(open(f, encoding="utf-8"))
    if e.get("parsed_ok"):
        continue
    try:
        parsed = B._extract_json(e.get("raw", ""))
    except (ValueError, json.JSONDecodeError):
        print("still unparsed:", f); continue
    e["summary"] = str(parsed.get("summary", ""))[:1500]
    e["categories"] = B.normalise_categories(parsed.get("categories"))
    e["parsed_ok"] = True
    json.dump(e, open(f, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n += 1; print("reparsed:", f)
print(n, "file(s) reparsed")
