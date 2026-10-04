"""Render an episode's animatic: the picture from the stage, the sound from the soundtrack.

    python3 -m studio.episode.render SLUG --stills 5 14 52.5      # PNGs of those instants, to review
    python3 -m studio.episode.render SLUG --video                  # the whole film, 1920x1080 at 24 fps, with sound
        episodes/<slug>/build/stills/<t>.png
        episodes/<slug>/<slug>_preview_tts.mp4

The video is cut into chunks rendered in parallel, then joined and muxed with build/master.wav. It is labelled as a
test run on screen: text-to-speech voices, stand-in props, no limb animation."""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
from PIL import Image, ImageDraw

from studio.episode import graphics, script
from studio.episode.puppet import Puppet, Sprite, blit
from studio.episode.stage import FPS, FRAME_W, PLATE, SPEAKER_COLOURS, Stage
from studio.episode.upscale import upscaled
from studio.paths import BACKGROUNDS

W, H = 1920, 1080
LO, HI = 0.62, 1.4                                   # puppet sprite sets: far shots and close shots
BG_SCALE = 2.0                                       # the plate is kept at twice its size for camera moves


class Renderer:
    def __init__(self, slug):
        self.slug = slug
        self.stage = Stage(slug)
        self.bg = upscaled(BACKGROUNDS / "tv-and-media" / "podcast-studio.png", BG_SCALE)
        self.puppets = {}
        for who, c in self.stage.cast.items():
            self.puppets[who] = {m: Puppet(c["character"], c["outfit"], master=m) for m in (LO, HI)}
        self.props, self.cards, self.strips = {}, {}, {}

    # ---------------------------------------------------------------- helpers
    def prop(self, kind, args, kwargs):
        key = (kind, tuple(args), tuple(sorted(kwargs.items())))
        if key not in self.props:
            self.props[key] = graphics.PROPS[kind](*args, **kwargs)
        return self.props[key]

    def card(self, name):
        if name not in self.cards:
            self.cards[name] = graphics.INSERTS[name](W, H)
        return self.cards[name]

    def strip(self, key, make):
        if key not in self.strips:
            self.strips[key] = make()
        return self.strips[key]

    def caption_strip(self, speaker, text):
        def make():
            img = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            f, fn = graphics.font(46), graphics.font(32)
            lines, cur = [], ""
            for w in text.split():
                if d.textlength(cur + " " + w, font=f) > 1500 and cur:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append(cur)
            b, g, r = SPEAKER_COLOURS[speaker]
            width = max(max(d.textlength(l, font=f) for l in lines), d.textlength(speaker.title(), font=fn)) + 70
            y = 170 - 16 - 54 * len(lines)
            d.rounded_rectangle([W / 2 - width / 2, y - 44, W / 2 + width / 2, 164], radius=18, fill=(0, 0, 0, 165))
            d.text((W / 2 - width / 2 + 22, y - 38), speaker.title(), font=fn, fill=(r, g, b, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
            for i, ln in enumerate(lines):
                d.text((W / 2, y + 54 * i + 22), ln, font=f, fill=(255, 255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, 255))
            return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGBA2BGRA)
        return self.strip(("cap", speaker, text), make)

    def title_strip(self, text):
        def make():
            img = Image.new("RGBA", (1100, 80), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, 1099, 79], radius=14, fill=(0, 0, 0, 160))
            d.text((24, 40), text, font=graphics.font(36), fill=(255, 255, 255, 255), anchor="lm")
            return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGBA2BGRA)
        return self.strip(("title", text), make)

    def mark_strip(self):
        def make():
            img = Image.new("RGBA", (620, 50), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, 619, 49], radius=10, fill=(0, 0, 0, 120))
            d.text((310, 25), "TEST RUN — TTS VOICES, STAND-IN PROPS", font=graphics.font(26), fill=(255, 210, 90, 255), anchor="mm")
            return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGBA2BGRA)
        return self.strip("mark", make)

    @staticmethod
    def paste(frame, bgra, x, y, alpha=1.0):
        h, w = bgra.shape[:2]
        x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, frame.shape[1]), min(y + h, frame.shape[0])
        if x1 <= x0 or y1 <= y0:
            return
        s = bgra[y0 - y:y1 - y, x0 - x:x1 - x]
        a = s[..., 3:4].astype(np.float32) / 255 * alpha
        roi = frame[y0:y1, x0:x1]
        roi[:] = (s[..., :3] * a + roi * (1 - a)).astype(np.uint8)

    # ------------------------------------------------------------------ frame
    def frame(self, t):
        st = self.stage.at(t)
        if st["end"] and not st["insert"]:
            a = min(1.0, (t - self.stage.tl["end_of_story"]) / 0.5)
            return (self.card("end_card") * a).astype(np.uint8)
        cx, cy, w = st["view"]
        h = w / FRAME_W
        x0, y0 = cx - w / 2, cy - h / 2
        sf = W / w
        A = np.array([[sf / BG_SCALE, 0, -x0 * sf], [0, sf / BG_SCALE, -y0 * sf]], np.float32)
        frame = cv2.warpAffine(self.bg, A, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if w < 1000:
            frame = cv2.GaussianBlur(frame, (0, 0), 1.6)               # a little depth of field in the closer shots
        to_frame = lambda x, y: ((x - x0) * sf, (y - y0) * sf)

        def draw_prop(p):
            spr = self.prop(p["kind"], p["args"], p["kwargs"])
            img = spr.img
            if p["crop"] is not None:
                n = max(1, int(img.shape[1] * p["crop"]))
                img = img[:, :n]
            fx, fy = to_frame(p["x"], p["y"])
            k = sf / graphics.SS * p["scale"]
            blit(frame, Sprite(img, 0, 0), np.array([[k, 0, fx - spr.ax * k], [0, k, fy - spr.ay * k], [0, 0, 1.0]]))

        for layer in ("far", "back"):
            for p in [p for p in st["props"] if p["z"] == layer]:
                draw_prop(p)
        drawables = [("char", c["y"], c) for c in st["chars"].values()] + [("prop", p["y"], p) for p in st["props"] if p["z"] == "y"]
        for kind, _, d in sorted(drawables, key=lambda i: i[1]):
            if kind == "prop":
                draw_prop(d)
                continue
            if d["x"] < x0 - 260 or d["x"] > x0 + w + 260:
                continue
            who = d["who"]
            pup = self.puppets[who][LO]
            sg = d["H"] / pup.guide_h * sf                                 # frame pixels per guide pixel
            pup = self.puppets[who][HI if sg >= 0.8 else LO]
            X, Y = to_frame(d["x"], d["y"])
            self.shadow(frame, X, to_frame(0, self.stage.floor)[1] + 4 * sf, d["H"] * 0.2 * sf)
            pup.draw(frame, X, Y, sg / pup.master, dict(mouth=d["mouth"], eyes=d["eyes"], gaze=d["gaze"], nod=d["nod"],
                                                        roll=d["roll"], squash=d["squash"]))
        for p in [p for p in st["props"] if p["z"] in ("held", "front")]:
            draw_prop(p)
        if st["insert"]:
            a = st["insert_alpha"]
            frame = (self.card(st["insert"]) * a + frame * (1 - a)).astype(np.uint8)
        if st["caption"]:
            self.paste(frame, self.caption_strip(*st["caption"]), 0, H - 170)
        if st["title"]:
            self.paste(frame, self.title_strip(st["title"][0]), 40, 36, st["title"][1])
        self.paste(frame, self.mark_strip(), W - 640, 20)
        return frame

    @staticmethod
    def shadow(frame, X, Y, r):
        if not (-r < X < frame.shape[1] + r):
            return
        x0, y0, x1, y1 = int(X - r * 1.3), int(Y - r * 0.3), int(X + r * 1.3), int(Y + r * 0.3)
        x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, frame.shape[1]), min(y1, frame.shape[0])
        if x1c <= x0c or y1c <= y0c:
            return
        roi = frame[y0c:y1c, x0c:x1c]
        dark = roi.copy()
        cv2.ellipse(dark, (int(X) - x0c, int(Y) - y0c), (int(r * 1.2), int(r * 0.22)), 0, 0, 360, (20, 16, 14), -1, cv2.LINE_AA)
        roi[:] = cv2.addWeighted(dark, 0.3, roi, 0.7, 0)


# ------------------------------------------------------------------------------------------------- video
def _chunk(args):
    slug, a, b, path = args
    r = Renderer(slug)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", path],
                          stdin=subprocess.PIPE)
    for i in range(a, b):
        ff.stdin.write(r.frame(i / FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    return path


def video(slug, workers=4, out=None):
    ep = script.episode_dir(slug)
    build = ep / "build"
    total = Stage(slug).total + 0.5
    n = int(total * FPS)
    per = (n + workers * 3 - 1) // (workers * 3)                       # more chunks than workers keeps them busy
    chunks = [(slug, a, min(n, a + per), str(build / f"part_{k:02d}.mp4")) for k, a in enumerate(range(0, n, per))]
    t0 = time.time()
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_chunk, chunks))
    (build / "parts.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    out = out or ep / f"{slug.replace('-', '_')}_preview_tts.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(build / "parts.txt"), "-i", str(build / "master.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    for p in parts:
        __import__("os").remove(p)
    print(f"{out}  {n} frames, {time.time() - t0:.0f}s", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.stills:
        r = Renderer(a.slug)
        d = script.episode_dir(a.slug) / "build" / "stills"
        d.mkdir(parents=True, exist_ok=True)
        for t in a.stills:
            f = d / f"{t:07.2f}.png"
            cv2.imwrite(str(f), r.frame(t))
            print(f, file=sys.stderr)
    if a.video:
        video(a.slug, a.workers)


if __name__ == "__main__":
    main()
