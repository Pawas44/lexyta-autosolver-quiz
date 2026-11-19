with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
matches = re.findall(r'ASSIGNMENTS\.[A-Z0-9_\.]+', text)
print(f"Total assignment translation keys: {len(matches)}")
for m in sorted(set(matches)):
    if any(k in m for k in ["RESUME", "START", "CONTINUE", "IN_PROGRESS", "ATTEMPT"]):
        print(" ", m)
