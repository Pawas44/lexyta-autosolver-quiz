with open("src/bot/telegram_server.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("def handle_update(")
if idx == -1: idx = text.find("def _poll_updates(")
if idx == -1: idx = text.find("def poll(")
if idx != -1:
    print(text[idx:idx+800])
else:
    # search for getUpdates
    idx_gu = text.find("getUpdates")
    print(text[idx_gu-100:idx_gu+600])
