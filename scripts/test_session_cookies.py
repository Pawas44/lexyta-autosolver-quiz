import sys
import os
sys.path.append(os.getcwd())

import json
from src.client.lexyta_api import LexytaAPIClient

with open("data/users.json", "r") as f:
    users = json.load(f)

u = list(users.values())[0]
print(f"Testing session for: {u['email']}")
client = LexytaAPIClient(u['email'], u['password'])
success = client.signin()
print("Signin success:", success)
print("Profile ID:", client.user_profile.get("id") if client.user_profile else "None")
print("Cookies received:")
for c in client.session.cookies:
    print(f"  {c.name} = {c.value[:25]}... (domain={c.domain}, path={c.path})")
