with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'\bC_\b', text)]
print(f"C_ occurrences: {len(matches)}")
for idx in matches[:5]:
    print(text[max(0, idx-50):idx+50])
    print("---")
