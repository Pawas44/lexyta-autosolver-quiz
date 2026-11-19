with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

idx = text.find("H as C_")
print(text[max(0, idx-200):idx+50])
