"""The web studio's server: the page (static/), a JSON API over the library and the episodes, and the files the
page shows (pictures, check sheets, stills, videos). Python's own http.server: nothing to install.

Uploads are sent as the request body (the file itself) with the details in the query string, so no form parsing
is needed: POST /api/characters?name=Roy%20Keane&filename=roy.png  <bytes>.

    GET  /api/library                         characters, backgrounds, settings, voices
    POST /api/characters?name=&role=&filename=           a new character from a picture
    POST /api/characters/<id>/sheets?filename=           another picture for a character
    GET  /api/characters/<id>/sheets                     the pictures a drawing can be cut from
    POST /api/characters/<id>/drawings  {name, sheet, box, faces}   (then it is cut out)
    POST /api/characters/<id>/build     {drawing}
    POST /api/characters/<id>/face      {drawing, eyes: [[x, y], [x, y]], mouth: [x, y]}   (built-drawing px)
    POST /api/backgrounds?title=&setting=&filename=     a new set
    POST /api/login {password}    GET /api/whoami      (STUDIO_PASSWORD set: everything else needs the login)
    GET  /api/shows  POST /api/shows {title}   GET|PUT|DELETE /api/shows/<slug>
    POST /api/shows/<slug>/pack?filename=[&offset=&total=]   the show's directive and assets
    POST /api/shows/<slug>/read                        read them (studio.web.autoprod --show)
    GET  /api/shows/<slug>/report
    POST /api/productions {title, show}                an episode to be produced from a pack (in a show): then
    POST /api/episodes/<slug>/pack?filename=[&offset=&total=]   every file of the pack (script, pictures,
                                                       recordings, zips), whole or in pieces
    POST /api/episodes/<slug>/produce {quality}        read the pack (studio.web.autoprod) and make the film
    GET  /api/episodes/<slug>/report                   what the import worked out
    GET  /api/episodes  POST /api/episodes {title}
    GET|PUT|DELETE /api/episodes/<slug>
    POST /api/episodes/<slug>/voice?cid=&filename=      a character's recording for the episode
    POST /api/episodes/<slug>/make {quality: draft|final}    POST /api/episodes/<slug>/stills {times}
    GET  /api/episodes/<slug>/stills
    GET  /api/jobs  GET /api/jobs/<id>  POST /api/jobs/<id>/cancel
    GET  /thumb?path=<repo path>&h=      GET /file/<repo path>     (library/, episodes/, build/ only)"""
import hashlib
import hmac
import json
import mimetypes
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from studio.paths import ROOT
from studio.web import jobs as J
from studio.web import projects as P

STATIC = Path(__file__).resolve().parent / "static"
SERVED = ("library/", "episodes/", "build/")
MAX_UPLOAD = 400 * 1024 * 1024

KOKORO_VOICES = {
    "bm_george": "British man: George", "bm_lewis": "British man: Lewis", "bm_daniel": "British man: Daniel",
    "bm_fable": "British man: Fable", "bf_emma": "British woman: Emma", "bf_isabella": "British woman: Isabella",
    "bf_alice": "British woman: Alice", "bf_lily": "British woman: Lily", "am_adam": "American man: Adam",
    "am_michael": "American man: Michael", "am_eric": "American man: Eric", "am_liam": "American man: Liam",
    "am_onyx": "American man: Onyx", "am_puck": "American man: Puck", "am_echo": "American man: Echo",
    "am_fenrir": "American man: Fenrir", "am_santa": "American man: Santa", "af_heart": "American woman: Heart",
    "af_bella": "American woman: Bella", "af_nicole": "American woman: Nicole", "af_sarah": "American woman: Sarah",
    "af_sky": "American woman: Sky", "af_nova": "American woman: Nova", "af_river": "American woman: River"}


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def repo_file(rel):
    """a path inside the served folders of the repository, or an error (no way out of them)"""
    rel = unquote(rel).lstrip("/")
    p = (ROOT / rel).resolve()
    if not any(str(p).startswith(str((ROOT / s).resolve()) + "/") for s in SERVED) or not p.is_file():
        raise ApiError("not found", 404)
    return p


# ---------------------------------------------------------------- the password
# STUDIO_PASSWORD set (always, when the studio is on the internet): every request but the page itself, its static
# files and the login needs the cookie the login gives. Unset: open (on your own machine).
PASSWORD = os.environ.get("STUDIO_PASSWORD", "")
SECRET = hashlib.sha256(("studio:" + os.environ.get("STUDIO_SECRET", "") + ":" + PASSWORD).encode()).hexdigest()
OPEN_PATHS = ("", "index.html", "static", "sw.js", "manifest.webmanifest", "healthz", "api/login", "api/whoami")


def token():
    return hmac.new(SECRET.encode(), b"studio-session", hashlib.sha256).hexdigest()


class Handler(BaseHTTPRequestHandler):
    server_version = "AnimationStudio/1.0"

    def log_message(self, fmt, *args):
        if "/api/jobs" not in (self.path or ""):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ plumbing
    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def send_file(self, p, ctype=None, cache=False):
        size = p.stat().st_size
        ctype = ctype or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        a, b = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m and size:
            if m.group(1):
                a = int(m.group(1))
                b = int(m.group(2)) if m.group(2) else size - 1
            else:
                a = max(0, size - int(m.group(2)))
            b = min(b, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1 if size else 0))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-cache")
        self.end_headers()
        if self.command == "HEAD" or not size:
            return
        with open(p, "rb") as f:
            f.seek(a)
            left = b - a + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ApiError("that file is too big (400 MB at most)")
        return self.rfile.read(n) if n else b""

    def json_body(self):
        b = self.body()
        return json.loads(b) if b else {}

    def authed(self):
        if not PASSWORD:
            return True
        for c in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = c.strip().partition("=")
            if k == "studio" and hmac.compare_digest(v, token()):
                return True
        return False

    def route(self, method):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        parts = [unquote(x) for x in u.path.strip("/").split("/") if x]
        try:
            path = "/".join(parts[:2]) if parts[:1] == ["api"] else (parts[0] if parts else "")
            if not self.authed() and path not in OPEN_PATHS:
                raise ApiError("log in first", 401)
            out = self.dispatch(method, parts, q)
            if out is not None:
                self.send_json(out)
        except ApiError as e:
            self.send_json(dict(error=str(e)), e.code)
        except FileExistsError as e:
            self.send_json(dict(error=str(e), exists=True), 409)
        except (ValueError, KeyError, FileNotFoundError) as e:
            self.send_json(dict(error=str(e)), 400)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send_json(dict(error=f"{type(e).__name__}: {e}"), 500)

    def do_GET(self):
        self.route("GET")

    def do_HEAD(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    # ------------------------------------------------------------ the routes
    def dispatch(self, method, parts, q):
        if not parts or parts[0] in ("index.html",):
            self.send_file(STATIC / "index.html", "text/html; charset=utf-8")
            return None
        head = parts[0]
        if head == "static" and len(parts) == 2 and (STATIC / parts[1]).is_file():
            self.send_file(STATIC / parts[1])
            return None
        if head in ("sw.js", "manifest.webmanifest"):          # the installable app (served from the root: its scope)
            self.send_file(STATIC / head, "text/javascript" if head.endswith(".js") else "application/manifest+json")
            return None
        if head == "healthz":
            return dict(ok=True)
        if parts == ["api", "whoami"]:
            return dict(authed=self.authed(), password=bool(PASSWORD))
        if parts == ["api", "login"] and method == "POST":
            if not PASSWORD or hmac.compare_digest(self.json_body().get("password", ""), PASSWORD):
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                b = json.dumps(dict(ok=True)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Set-Cookie", f"studio={token()}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax{secure}")
                self.end_headers()
                self.wfile.write(b)
                return None
            import time
            time.sleep(1.0)                                    # slow down guessing
            raise ApiError("wrong password", 403)
        if head == "file":
            self.send_file(repo_file("/".join(parts[1:])))
            return None
        if head == "thumb":
            a = q.get("alpha") == "1"
            self.send_file(P.thumb(str(repo_file(q["path"]).relative_to(ROOT)), int(q.get("h", 320)), a),
                           "image/png" if a else "image/jpeg", True)
            return None
        if head == "charthumb" and len(parts) == 2:
            t = P.character_thumb(parts[1])
            if not t:
                raise ApiError("no picture", 404)
            self.send_file(t, "image/jpeg")
            return None
        if head != "api" or len(parts) < 2:
            raise ApiError("not found", 404)
        what, rest = parts[1], parts[2:]
        if what == "library" and method == "GET":
            return dict(characters=P.characters(), backgrounds=P.backgrounds(), settings=P.SETTINGS,
                        voices=KOKORO_VOICES, tones=sorted(__import__("studio.film.perf", fromlist=["TAGS"]).TAGS))
        if what == "characters":
            return self.characters(method, rest, q)
        if what == "backgrounds" and method == "POST":
            bid = P.add_background(q.get("title", ""), q.get("setting", ""), self.body(), q.get("filename", "set.png"),
                                   q.get("crop", "1") == "1")
            return dict(id=bid)
        if what == "productions" and method == "POST":
            b = self.json_body()
            return dict(slug=P.new_production(b.get("title", ""), b.get("show", "")))
        if what == "shows":
            return self.shows(method, rest, q)
        if what == "episodes":
            return self.episodes(method, rest, q)
        if what == "jobs":
            if not rest:
                return J.QUEUE.list()
            j = J.QUEUE.get(rest[0])
            if not j:
                raise ApiError("no such job", 404)
            if len(rest) > 1 and rest[1] == "cancel" and method == "POST":
                J.QUEUE.cancel(j.id)
            return j.view(tail=int(q.get("tail", 80)))
        raise ApiError("not found", 404)

    def characters(self, method, rest, q):
        if not rest and method == "POST":
            cid = P.add_character(q.get("name", ""), self.body(), q.get("filename", "drawing.png"), q.get("role", ""))
            job = J.QUEUE.add(J.build_character(cid, "front"))
            return dict(id=cid, job=job.id)
        if not rest:
            raise ApiError("not found", 404)
        cid = rest[0]
        if not (P.CHARACTERS / cid / "character.yaml").exists():
            raise ApiError(f"no character {cid}", 404)
        sub = rest[1] if len(rest) > 1 else ""
        if sub == "sheets" and method == "GET":
            return P.sheets(cid)
        if sub == "sheets" and method == "POST":
            return dict(sheet=P.add_reference(cid, self.body(), q.get("filename", "sheet.png")))
        if sub == "drawings" and method == "POST":
            b = self.json_body()
            box = [int(round(v)) for v in b["box"]]
            if box[2] - box[0] < 20 or box[3] - box[1] < 20:
                raise ApiError("the box is too small")
            name = P.set_drawing(cid, b.get("name") or "front", dict(sheet=b["sheet"], box=box, faces=b.get("faces", "F")))
            job = J.QUEUE.add(J.build_character(cid, name))
            return dict(drawing=name, job=job.id)
        if sub == "build" and method == "POST":
            b = self.json_body()
            return dict(job=J.QUEUE.add(J.build_character(cid, b["drawing"])).id)
        if sub == "face" and method == "POST":
            b = self.json_body()
            mk = P.set_face(cid, b["drawing"], b["eyes"], b["mouth"])
            job = J.QUEUE.add(J.Job(f"Face for {cid}: {b['drawing']}", [("Measure the face",
                                    [J.PY, "-m", "studio.film.art", cid, b["drawing"]])], "character", cid))
            return dict(marks=mk, job=job.id)
        if sub == "drawing" and len(rest) > 2 and method == "GET":
            f = P.BUILD / "film" / cid / f"{rest[2]}.png"
            if not f.exists():
                raise ApiError("not built yet", 404)
            meta = json.loads((P.BUILD / "film" / cid / "meta.json").read_text()).get(rest[2], {})
            marks = json.loads((P.BUILD / "film" / cid / "marks.json").read_text()).get(rest[2], {})
            return dict(path=str(f.relative_to(ROOT)), meta=meta, marks=marks)
        raise ApiError("not found", 404)

    def pack_upload(self, slug, q, root):
        """a file of a pack, whole or in pieces (offset, total: a phone's upload of a big zip survives a dropped
        connection and any limit on a request's size)"""
        if not (root / slug).exists():
            raise ApiError("no such production", 404)
        name = q.get("filename", "file")
        data = self.body()
        if "total" not in q:
            return dict(file=P.add_to_pack(slug, data, name, root))
        off, total = int(q.get("offset", 0)), int(q["total"])
        part = root / slug / "build" / "uploads" / (P.sha(name.encode())[:16] + ".part")
        part.parent.mkdir(parents=True, exist_ok=True)
        have = part.stat().st_size if part.exists() else 0
        if off == 0:
            part.write_bytes(b"")
            have = 0
        if off != have:
            return dict(offset=have)                         # resume from what arrived
        with open(part, "ab") as f:
            f.write(data)
        have += len(data)
        if have < total:
            return dict(offset=have)
        out = P.add_to_pack(slug, part.read_bytes(), name, root)
        part.unlink()
        return dict(file=out, offset=have)

    def shows(self, method, rest, q):
        if not rest:
            if method == "POST":
                return dict(slug=P.new_show(self.json_body().get("title", "")))
            return P.shows()
        slug, sub = rest[0], (rest[1] if len(rest) > 1 else "")
        if not sub:
            if method == "GET":
                return P.load_show(slug)
            if method == "PUT":
                P.load_show(slug)
                return P.save_show(slug, self.json_body())
            if method == "DELETE":
                P.delete_show(slug)
                return dict(ok=True)
        if sub == "pack" and method == "POST":
            return self.pack_upload(slug, q, P.SHOWS)
        if sub == "read" and method == "POST":
            P.load_show(slug)
            return dict(job=J.QUEUE.add(J.read_show(slug)).id)
        if sub == "report" and method == "GET":
            return P.report(slug, P.SHOWS) or {}
        raise ApiError("not found", 404)

    def episodes(self, method, rest, q):
        if not rest:
            if method == "POST":
                return dict(slug=P.new_episode(self.json_body().get("title", "")))
            return P.episodes()
        slug = rest[0]
        sub = rest[1] if len(rest) > 1 else ""
        if not sub:
            if method == "GET":
                return P.load_episode(slug)
            if method == "PUT":
                P.load_episode(slug)
                return P.save_episode(slug, self.json_body())
            if method == "DELETE":
                P.delete_episode(slug)
                return dict(ok=True)
        if sub == "pack" and method == "POST":
            return self.pack_upload(slug, q, P.EPISODES)
        if sub == "produce" and method == "POST":
            if not (P.EPISODES / slug / "pack").exists():
                raise ApiError("upload the pack first")
            b = self.json_body()
            return dict(job=J.QUEUE.add(J.make_episode(slug, b.get("quality", "final") != "final", pack=True)).id)
        if sub == "report" and method == "GET":
            return P.report(slug) or {}
        if sub == "voice" and method == "POST":
            return dict(file=P.add_voice(slug, q["cid"], self.body(), q.get("filename", "voice.wav")))
        if sub == "make" and method == "POST":
            P.load_episode(slug)
            b = self.json_body()
            return dict(job=J.QUEUE.add(J.make_episode(slug, b.get("quality", "draft") != "final")).id)
        if sub == "stills" and method == "POST":
            P.load_episode(slug)
            ts = [float(t) for t in self.json_body().get("times", []) if t != "auto"][:16]   # none: every shot
            return dict(job=J.QUEUE.add(J.stills(slug, ts)).id)
        if sub == "stills" and method == "GET":
            d = P.EPISODES / slug / "build" / "stills"
            fs = sorted(d.glob("still_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)[:24] if d.exists() else []
            return [dict(path=str(p.relative_to(ROOT)), t=float(p.stem[6:]), mtime=p.stat().st_mtime) for p in fs]
        if sub == "outputs" and method == "GET":
            d = P.EPISODES / slug
            out = {}
            for k, p in (("video", d / f"{slug}.mp4"), ("preview", d / f"{slug}_preview.mp4"),
                         ("contact", d / "build" / "contact.jpg"), ("lips", d / "build" / "lips.jpg")):
                if p.exists():
                    out[k] = dict(path=str(p.relative_to(ROOT)), mtime=p.stat().st_mtime)
            tl = d / "build" / "lines.json"
            if tl.exists():
                out["lines"] = {k: dict(dur=v["dur"], text=v["text"]) for k, v in json.loads(tl.read_text()).items()}
            return out
        raise ApiError("not found", 404)


def serve(host="127.0.0.1", port=8000):
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    print(f"Animation Studio: http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
