with open("src/bot/telegram_server.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("def send_message(")
if idx != -1:
    print(text[idx:idx+800])
