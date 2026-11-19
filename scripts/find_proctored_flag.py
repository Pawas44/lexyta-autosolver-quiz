with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
matches = re.findall(r'.{0,40}(?:proctored|is_proctored|enable_proctoring|proctoring_enabled).{0,60}', text, flags=re.I)
print(f"Matches for proctored flag: {len(matches)}")
for m in matches[:10]:
    print(" ->", m.strip())
