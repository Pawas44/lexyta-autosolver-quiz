with open("src/bot/telegram_server.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find('handle_message')
while idx != -1:
    print(f"Index {idx}:")
    print(text[max(0, idx-50):idx+120])
    print("---")
    idx = text.find('handle_message', idx+1)
