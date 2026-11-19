with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
idx = text.find("cookieService.get(")
if idx != -1:
    print("=== Cookie Service Usage ===")
    print(text[max(0, idx-100):idx+300])

# Find session cookie name
cookies = re.findall(r'this\.cookieService\.[a-zA-Z]+\(([^)]+)\)', text)
print("Cookie calls:", cookies[:10])
