import re

with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# More flexible selector search
print("=== ALL ANGULAR SELECTORS ===")
for m in re.finditer(r'selectors:\[\[`(lexyta-[^`]+)`\]\]', text):
    sel = m.group(1)
    if any(k in sel for k in ["quiz","question","option","attempt","section","answer","assign","proctor"]):
        print(f"  <{sel}>")

# Find question answered / answer save
print("\n=== QUESTION_ANSWERED and answer save ===")
for m in re.finditer(r'QUESTION_ANSWERED', text):
    idx = m.start()
    print(text[max(0,idx-200):idx+400])
    print("---")

# Find where options/choices are rendered
print("\n=== OPTION / CHOICE RENDERING ===")
for kw in ["option_id", "choice_id", "selected_option", "is_correct", "radio", "checkbox"]:
    matches = list(re.finditer(re.escape(kw), text, re.I))
    if matches:
        print(f"\n[{kw}] found {len(matches)} times:")
        for m in matches[:3]:
            idx = m.start()
            print(f"  ...{text[max(0,idx-80):idx+200]}")
            print("  ---")
