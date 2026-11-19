with open("src/bot/telegram_server.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'callback_query', text)]
print(f"callback_query matches: {len(matches)}")
for idx in matches[:3]:
    print(text[max(0, idx-50):idx+200])

matches_rm = [m.start() for m in re.finditer(r'reply_markup', text)]
print(f"reply_markup matches: {len(matches_rm)}")
for idx in matches_rm[:3]:
    print(text[max(0, idx-50):idx+200])
