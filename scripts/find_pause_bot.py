with open("src/bot/telegram_server.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'set_user_active', text)]
for idx in matches:
    print(text[max(0, idx-100):idx+300])
    print("---")

matches_pause = [m.start() for m in re.finditer(r'pause', text, re.I)]
for idx in matches_pause:
    print(text[max(0, idx-100):idx+300])
    print("---")
