"""Drives a running web studio through its API the way the phone app does, and fails loudly if any step breaks:
log in, add a new cast member and a new background, upload a director's zip and production notes (in pieces),
produce a draft, and check the film came out with the right cast and set.

    python3 tools/smoke_web.py http://localhost:8000 PASSWORD

Used by .github/workflows/studio-image.yml against the Docker image; harmless to run by hand (it makes a cast member
"Smoke Tester", a background "Smoke Test Shed" and an episode, and deletes the episode at the end)."""
import io
import json
import sys
import time
import urllib.request
import zipfile
from http.cookiejar import CookieJar
from urllib.parse import quote

from PIL import Image, ImageDraw

BASE, PASSWORD = sys.argv[1].rstrip("/"), sys.argv[2]
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def call(method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path}: {e.code} {e.read()[:300]!r}")


def png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


step("health and login")
for _ in range(60):
    try:
        if json.loads(urllib.request.urlopen(BASE + "/healthz", timeout=5).read())["ok"]:
            break
    except Exception:  # noqa: BLE001  (still starting)
        time.sleep(2)
assert call("GET", "/api/whoami")["password"], "the studio must have a password"
call("POST", "/api/login", {"password": PASSWORD})
lib = call("GET", "/api/library")
step(f"library: {len(lib['characters'])} characters, {len(lib['backgrounds'])} sets")

step("a new cast member, named from the file (a cartoon face drawn here, on transparent)")
im = Image.new("RGBA", (400, 900), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((90, 330, 310, 860), 40, fill=(40, 60, 160, 255), outline=(10, 10, 10, 255), width=8)
d.ellipse((80, 40, 320, 320), fill=(240, 200, 160, 255), outline=(10, 10, 10, 255), width=8)
for x in (150, 250):
    d.ellipse((x - 32, 120, x + 32, 190), fill=(255, 255, 255, 255), outline=(10, 10, 10, 255), width=6)
    d.ellipse((x - 12, 140, x + 12, 170), fill=(10, 10, 10, 255))
d.line((150, 250, 250, 250), fill=(10, 10, 10, 255), width=8)
r = call("POST", "/api/characters?filename=" + quote("Smoke_Tester-final.png"), raw=png(im))
cid = r.get("id", "smoke-tester")
step(f"cast member: {cid}")

step("a new background")
bg = Image.new("RGB", (1920, 1080), (120, 160, 200))
ImageDraw.Draw(bg).rectangle((0, 700, 1920, 1080), fill=(90, 120, 70))
call("POST", "/api/backgrounds?setting=auto&filename=" + quote("Smoke Test Shed.png"), raw=png(bg))

step("the director's zip and production notes, uploaded in pieces")
script = """# SMOKE TEST — EPISODE 1

## SCENE 1 — THE SHED

**INT. SMOKE TEST SHED. DAY.**

[L001] SMOKE: Gary, this is a test of the whole studio.
[L002] GARY: Then let's hope it passes.
[L003] SMOKE: (dry) It had better.
"""
z = io.BytesIO()
with zipfile.ZipFile(z, "w") as zf:
    zf.writestr("Director pack/script.md", script)
    zf.writestr("Director pack/notes.md", "Speaking cast: Smoke Tester, Gary Neville.\n")
slug = call("POST", "/api/productions", {})["slug"]
for name, blob in (("Director pack.zip", z.getvalue()), ("Production notes.txt", b"Scene 1 plays in the shed.\n")):
    off, CH = 0, 300
    while True:
        r = call("POST", f"/api/episodes/{slug}/pack?filename={quote(name)}&offset={off}&total={len(blob)}",
                 raw=blob[off:off + CH])
        off = r["offset"]
        if r.get("file"):
            break
job = call("POST", f"/api/episodes/{slug}/produce", {"quality": "draft"})["job"]

step(f"producing {slug} (job {job})")
seen = 0
while True:
    j = call("GET", f"/api/jobs/{job}?tail=400")
    for line in j["log"][seen:] if len(j["log"]) > seen else []:
        print("   " + line, flush=True)
    seen = len(j["log"])
    if j["state"] in ("done", "failed", "cancelled"):
        break
    time.sleep(5)
if j["state"] != "done":
    raise SystemExit(f"production {j['state']}: {j['error']}")

rep = call("GET", f"/api/episodes/{slug}/report")
ep = call("GET", f"/api/episodes/{slug}")
out = call("GET", f"/api/episodes/{slug}/outputs")
step(f"cast {rep['characters']}; scenes {rep['scenes']}")
assert rep["characters"]["SMOKE"]["id"] == cid, rep["characters"]
assert rep["characters"]["GARY"]["id"] == "gary-neville", rep["characters"]
assert ep["scenes"][0]["background"].endswith("smoke-test-shed"), ep["scenes"]
assert out.get("preview"), out
assert len(out["lines"]) == 3, out["lines"]
size = len(opener.open(BASE + "/file/" + quote(out["preview"]["path"])).read())
assert size > 50_000, size
step(f"the draft film: {out['preview']['path']} ({size // 1024} KB) - all good")
call("DELETE", f"/api/episodes/{slug}")
