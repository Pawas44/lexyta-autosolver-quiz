with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
keywords = ["geolocation", "getCurrentPosition", "ip_address", "client_ip", "remote_ip", "location.country", "geo_ip"]
for kw in keywords:
    matches = list(re.finditer(re.escape(kw), text, re.I))
    print(f"Keyword '{kw}': {len(matches)} matches")
    for m in matches[:3]:
        i = m.start()
        print("  ...", text[max(0, i-50):i+150])
