import re

with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Find all selectors
print("=== ALL LEXYTA ANGULAR SELECTORS ===")
selectors = re.findall(r'selectors:\[\[`(lexyta-[^`]+)`\]\]', text)
for s in sorted(set(selectors)):
    print(f"  <{s}>")

# Find quiz attempt page component
print("\n\n=== QUIZ ATTEMPT COMPONENT SEARCH ===")
for kw in ["quiz-attempt", "quiz-view", "quiz-section", "quiz-question", "quiz-option",
            "assignment-attempt", "attempt-view", "question-card", "answer-option",
            "question-view", "quiz-player", "quiz-runner"]:
    idx = text.find(kw)
    if idx != -1:
        print(f"\n[{kw}] found at offset {idx}:")
        print(text[max(0,idx-200):idx+500])
        print("---")

# Search for where sections/questions are iterated in templates
print("\n\n=== TEMPLATE ITERATION PATTERNS ===")
for m in re.finditer(r'(?:ngFor|ngForOf|ngIf|@for|@if)[^}]*(?:question|option|section|answer)', text, re.I):
    idx = m.start()
    print(text[max(0,idx-50):idx+300])
    print("---")
