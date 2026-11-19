import re

with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# 1. Search for COUNTER_ROLLBACK context
idx = text.find("COUNTER_ROLLBACK")
if idx != -1:
    print("=== COUNTER_ROLLBACK context ===")
    print(text[max(0, idx-300):idx+800])
    print("\n" + "="*50 + "\n")

# 2. Search for multiple session / concurrent / login checks
keywords = [
    "multiple tabs", "multiple devices", "another session", "concurrent",
    "already in progress", "active_attempt", "attemptIsInProgress",
    "close-in-progress", "single_session", "session_expired", "unauthorized",
    "401", "403", "ATTEMPT_STARTED", "ATTEMPT_SUBMITTED"
]

for kw in keywords:
    matches = list(re.finditer(re.escape(kw), text, re.I))
    if matches:
        print(f"=== Keyword: '{kw}' ({len(matches)} matches) ===")
        for m in matches[:3]:
            i = m.start()
            print("  ...", text[max(0, i-100):i+200])
            print("  ---")
