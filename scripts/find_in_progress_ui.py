with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'attemptIsInProgress', text)]
for idx in matches:
    print("--- Occurrence ---")
    print(text[max(0, idx-200):idx+400])
