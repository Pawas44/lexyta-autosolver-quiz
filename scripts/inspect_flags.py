with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

idx = text.find("flagReasons:{")
if idx != -1:
    print(text[idx:idx+1500])
