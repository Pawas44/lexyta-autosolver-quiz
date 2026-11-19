with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

idx = text.find("cookieService.get(C_)")
if idx != -1:
    print(text[idx-500:idx+100])
