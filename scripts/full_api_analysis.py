import re

with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Find Cn$1 (proctoring API service)
for m in re.finditer(r'Cn\$1', text):
    idx = m.start()
    snippet = text[max(0,idx-100):idx+200]
    if "class" in snippet or "baseUrl" in snippet or "http" in snippet or "proctoring" in snippet.lower():
        print("=== Cn$1 usage ===")
        print(snippet)
        print("---")

# Find the proctoring API service class
print("\n\n=== PROCTORING API CLASS ===")
for m in re.finditer(r'class\s+\w+\{[^}]*proctoring[^}]*\}', text, re.I):
    print(text[m.start()-50:m.end()+200])

# Find all HTTP calls related to proctoring
print("\n\n=== HTTP PROCTORING CALLS ===")
for m in re.finditer(r'this\.http\.\w+\([^)]*proctor[^)]*\)', text, re.I):
    idx = m.start()
    print(text[max(0,idx-80):idx+300])
    print("---")

# Find where quiz view questions are fetched (student side)
print("\n\n=== QUIZ VIEW / STUDENT ATTEMPT APIS ===")
for term in ["quiz/view", "quiz/attempt", "student/assignments", "attempts/start", "attempts/submit", "attempts/latest", "/answer"]:
    for m in re.finditer(re.escape(term), text, re.I):
        idx = m.start()
        print(f"[{term}]:", text[max(0,idx-100):idx+200])
        print("---")
