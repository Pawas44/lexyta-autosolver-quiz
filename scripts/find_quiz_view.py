import re

with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Find the quiz view section by looking for quiz/view API consumer
idx = text.find("getStudentQuizView")
if idx != -1:
    # Find where it's called
    for m in re.finditer(r'getStudentQuizView\(', text):
        i = m.start()
        print("=== getStudentQuizView CALL SITE ===")
        print(text[max(0,i-300):i+800])
        print("===\n\n")

# Find submitAssignmentAttempt call site
idx = text.find("submitAssignmentAttempt")
if idx != -1:
    for m in re.finditer(r'submitAssignmentAttempt\(', text):
        i = m.start()
        print("=== submitAssignmentAttempt CALL SITE ===")
        print(text[max(0,i-300):i+800])
        print("===\n\n")

# Find sections rendering
print("\n=== QUIZ SECTION / QUESTION RENDERING ===")
for kw in ["section", "sections"]:
    for m in re.finditer(rf'\.{kw}\(\)\s*\??\.', text):
        i = m.start()
        snippet = text[max(0,i-100):i+300]
        if "question" in snippet.lower() or "quiz" in snippet.lower():
            print(snippet)
            print("---")
