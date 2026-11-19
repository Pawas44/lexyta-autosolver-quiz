with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
matches = re.findall(r'C_\s*=\s*[`\'"][^`\'"]+[`\'"]', text)
print("Matches:", matches)
