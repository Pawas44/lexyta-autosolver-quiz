import re

with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Find Angular component selectors related to quiz/question/option
print("=== ANGULAR COMPONENT SELECTORS (quiz/question/option) ===")
for m in re.finditer(r'selectors:\[\[`([^`]*(?:quiz|question|option|attempt|section|answer|choice)[^`]*)`\]\]', text, re.I):
    print(f"  Component: <{m.group(1)}>")

# Find CSS classes used in quiz components
print("\n=== CSS CLASSES IN QUIZ COMPONENTS ===")
for m in re.finditer(r'selectors:\[\[`[^`]*(?:quiz|question)[^`]*`\]\][^}]*consts:\[([^\]]*)\]', text, re.I):
    classes = re.findall(r'`([^`]+)`', m.group(1))
    print(f"  Classes: {classes[:20]}")

# Find how quiz questions/options are rendered (template patterns)
print("\n=== QUIZ QUESTION RENDERING ===")
quiz_component_start = text.find("lexyta-quiz")
if quiz_component_start != -1:
    print(text[quiz_component_start-200:quiz_component_start+800])

# Find answer submission format
print("\n=== ANSWER SUBMISSION PAYLOAD ===")
for m in re.finditer(r'submit[^(]*\([^)]*\)[^{]*\{[^}]*', text, re.I):
    snippet = text[m.start():m.start()+500]
    if "answer" in snippet.lower() or "option" in snippet.lower() or "selected" in snippet.lower():
        print(snippet[:500])
        print("---")

# Find question type enum
print("\n=== QUESTION TYPE ENUM ===")
for m in re.finditer(r'MULTIPLE_CHOICE|SINGLE_CHOICE|TRUE_FALSE|FILL_IN|ESSAY|SHORT_ANSWER|MATCHING', text):
    idx = m.start()
    print(text[max(0,idx-80):idx+200])
    print("---")
