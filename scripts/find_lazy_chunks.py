import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# First, find ALL lazy-loaded chunk filenames from main bundle
with open("scripts/chunks/main-RCXULGX4.js", "r", encoding="utf-8", errors="ignore") as f:
    main = f.read()

# Angular lazy route patterns: loadComponent/loadChildren with import("./chunk-...")
lazy_chunks = set(re.findall(r'["\'](\./chunk-[A-Za-z0-9_\-]+\.js)["\']', main))
# Also look for the chunk map pattern: "HASH":"chunk-NAME.js"
chunk_map = set(re.findall(r'"([A-Za-z0-9_\-]+\.js)"', main))
# And direct references
direct_refs = set(re.findall(r'["\']([a-zA-Z0-9_\-]+\.js)["\']', main))

all_js = set()
for s in lazy_chunks | chunk_map | direct_refs:
    name = s.replace("./", "")
    if "chunk" in name or "lazy" in name:
        all_js.add(name)

print(f"Found {len(all_js)} chunk references")
for n in sorted(all_js):
    print(f"  {n}")

# Now try common Angular lazy-load pattern: the webpack/esbuild chunk-map
# Look for a big object mapping routes to chunk filenames
route_map = re.findall(r'(?:path|loadComponent|loadChildren)[^}]*import\(["\']([^"\']+)["\']', main)
print(f"\nLazy route imports: {len(route_map)}")
for r_ in route_map[:20]:
    print(f"  {r_}")

# Also search for esbuild-style chunk reference in scripts-YZ5DFNR2.js
print("\n\nChecking scripts-YZ5DFNR2.js for chunk map...")
try:
    with open("scripts/chunks/chunk-CSls11qI.js", "r", encoding="utf-8", errors="ignore") as f:
        scripts = f.read()
    more_chunks = set(re.findall(r'["\'](\./chunk-[A-Za-z0-9_\-]+\.js)["\']', scripts))
    print(f"Found {len(more_chunks)} more chunk refs in chunk-CSls11qI.js")
    for c in sorted(more_chunks):
        print(f"  {c}")
except:
    pass

# Try fetching scripts-YZ5DFNR2.js for chunk map
r = requests.get("https://lms.lexyta.com/scripts-YZ5DFNR2.js", headers=headers, timeout=15)
scripts_text = r.text
more = set(re.findall(r'["\'](\./chunk-[A-Za-z0-9_\-]+\.js)["\']', scripts_text))
print(f"\nscripts-YZ5DFNR2.js chunk refs: {len(more)}")
for c in sorted(more):
    print(f"  {c}")

# Search for route definitions with 'quiz' or 'assignment' or 'attempt' in paths
print("\n\n=== ROUTES WITH QUIZ/ASSIGNMENT ===")
for m in re.finditer(r'path:\s*`([^`]*(?:quiz|assignment|attempt|exam)[^`]*)`', main, re.I):
    print(f"  Route: /{m.group(1)}")
