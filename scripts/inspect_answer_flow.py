with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
# Find how answers are saved or updated during quiz taking
matches = re.findall(r'.{0,40}(?:saveAnswer|selectOption|updateAnswer|answers\[|setAnswer|answerQuestion).{0,60}', text, flags=re.I)
print(f"Matches: {len(matches)}")
for m in matches[:10]:
    print(" ->", m.strip())

print("\n--- Look for submitAssignmentAttempt payload structure ---")
idx = text.find("submitAssignmentAttempt(")
if idx != -1:
    print(text[idx-100:idx+800])
