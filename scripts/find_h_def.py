with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
m = re.findall(r'\bvar H\s*=\s*[`\'"][^`\'"]+[`\'"]', text)
print("H is:", m)
