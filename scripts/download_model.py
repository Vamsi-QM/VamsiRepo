import urllib.request, os

REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEST = os.path.join("D:", os.sep, "VamsiCompanion", "models", FILE)
URL = f"https://huggingface.co/{REPO}/resolve/main/{FILE}"

os.makedirs(os.path.dirname(DEST), exist_ok=True)
tmp = DEST + ".part"

req = urllib.request.Request(URL, headers={"User-Agent": "opencode"})
with urllib.request.urlopen(req, timeout=3600) as r, open(tmp, "wb") as f:
    total = int(r.headers.get("Content-Length") or 0)
    done = 0
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        f.write(chunk)
        done += len(chunk)
os.replace(tmp, DEST)
print("DONE", DEST, round(done / 1048576, 1), "MB")
