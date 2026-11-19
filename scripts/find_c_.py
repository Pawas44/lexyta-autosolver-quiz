with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
m = re.search(r'var C_\s*=\s*[`\'"]([^`\'"]+)[`\'"]', text)
if m:
    print("C_ is:", m.group(1))
else:
    # search where C_ is defined
    idx = text.find("C_=")
    if idx == -1: idx = text.find("C_ =")
    if idx != -1:
        print(text[idx-50:idx+100])
