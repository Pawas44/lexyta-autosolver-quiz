with open("src/bot/telegram_server.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("offset = update[\"update_id\"] + 1")
print(text[idx:idx+800])
