"""What the picture shows at any instant of an episode.

    stage = Stage("the-appeals-department")
    s = stage.at(t)        # camera view, who is where doing what, props, insert card, caption

Built from the timeline (when each line and direction happens), the lip-sync cues (mouth shapes), and the episode's
staging.yaml and shots.yaml (see their headers). Everything is anchored to script beats, so when the voices change
the picture retimes with them. Coordinates are the studio plate's pixels (1672 x 941).

Acting here is replacement animation: the figure holds its pose and breathes; the head nods with the voice and
turns its eyes to whoever it is talking to or listening to; the mouth follows the voice; eyes blink. Entrances and
exits are bobbing slides; the sit, the recoil and the freeze are squashes and drops. There are no arm or leg moves in
this version: held things (the reader, the clipboard, the mug) float in front of the hand, and the kit's assembled
figure carries the body."""
import json
import math

import numpy as np
import soundfile as sf
import yaml

from studio.episode import script
from studio.paths import CHARACTERS

FPS = 24
PLATE = (1672, 941)
FRAME_W = 16.0 / 9.0
SPEAKER_COLOURS = dict(GARY=(255, 190, 110), ROY=(140, 235, 150), MICAH=(120, 225, 255), RONALDO=(120, 130, 255),
                       PEP=(235, 235, 235))        # BGR, for captions
STRIDE = 58.0                                       # plate pixels per step of a walking slide


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


class Stage:
    def __init__(self, slug):
        self.slug = slug
        ep = script.episode_dir(slug)
        self.tl = json.loads((ep / "build" / "timeline.json").read_text())
        self.items = {i["id"]: i for i in self.tl["items"]}
        self.lines = [i for i in self.tl["items"] if i["kind"] == "line"]
        self.cast = script.load_cast(slug)
        self.stg = yaml.safe_load((ep / "staging.yaml").read_text())
        self.shots = yaml.safe_load((ep / "shots.yaml").read_text())
        self.cues = json.loads((ep / "build" / "lipsync.json").read_text())
        self.scenes = {s.n: s for s in script.load(slug)}
        self.total = self.tl["total"]
        self.floor = self.stg["floor_y"]
        self.names = list(self.cast)
        self.height = {}
        for n, c in self.cast.items():
            info = yaml.safe_load((CHARACTERS / c["character"] / "character.yaml").read_text())
            self.height[n] = info.get("height_cm", 180) * self.stg["height_px_per_cm"]
        self._tracks()
        self._blinks()
        self._envelopes(ep)
        self._shots()
        self._props()

    # ------------------------------------------------------------------ time
    def T(self, spec, key_at="at", key_from="from", key_off="off"):
        it = self.items[spec[key_at]]
        return (it["start"] if spec.get(key_from, "start") == "start" else it["end"]) + spec.get(key_off, 0.0)

    # ------------------------------------------------------------ characters
    def _tracks(self):
        self.segs = {n: [] for n in self.names}
        pos = {n: self.stg["characters"][n]["x"] for n in self.names}
        for m in sorted(self.stg["moves"], key=self.T):
            t0 = self.T(m)
            self.segs[m["who"]].append(dict(t0=t0, t1=t0 + m["dur"], a=pos[m["who"]], b=m["to"], style=m["style"]))
            pos[m["who"]] = m["to"]
        self.actions = {n: sorted([dict(a, t=self.T(a)) for a in self.stg["actions"] if a["who"] == n], key=lambda a: a["t"]) for n in self.names}

    def x_at(self, who, t):
        """(x, walking bob in plate px, roll in degrees)"""
        x = self.stg["characters"][who]["x"]
        bob = roll = 0.0
        for s in self.segs[who]:
            if t >= s["t1"]:
                x = s["b"]
            elif t >= s["t0"]:
                p = (t - s["t0"]) / (s["t1"] - s["t0"])
                x = lerp(s["a"], s["b"], ease(p))
                if s["style"] == "walk":
                    phase = p * abs(s["b"] - s["a"]) / STRIDE
                    bob = -9.0 * abs(math.sin(math.pi * phase))
                    roll = 2.6 * math.sin(math.pi * phase) * (1 if s["b"] >= s["a"] else -1)
                break
            else:
                break
        return x, bob, roll

    def pose_at(self, who, t):
        """(sink in plate px, squash (sx, sy), frozen)"""
        sink, sy, hop, frozen = 0.0, 1.0, 0.0, False
        H = self.height[who]
        level = 0.0                                     # how far seated: 0 standing, 1 seated
        for a in self.actions[who]:
            if t < a["t"]:
                break
            if a["do"] == "sit":
                level = ease((t - a["t"]) / a["dur"])
            elif a["do"] == "stand":
                level = 1 - ease((t - a["t"]) / a["dur"])
            elif a["do"] == "freeze":
                frozen = frozen or t < self.T(a["until"])
            elif a["do"] == "recoil":
                u = t - a["t"]
                if u < 0.25:                            # lower, a tiny anticipation
                    sy = lerp(1.0, 0.88, ease(u / 0.25))
                elif u < 0.5:                           # and spring back up
                    p = ease((u - 0.25) / 0.25)
                    sy = lerp(0.88, 1.05, p)
                    hop = -34 * math.sin(math.pi * p)
                elif u < 0.85:
                    sy = lerp(1.05, 1.0, ease((u - 0.5) / 0.35))
        sink = 0.22 * H * level + hop
        sy *= 1 - 0.035 * level
        return sink, (1.0 + (1 - sy) * 0.4, sy), frozen

    def speaker_at(self, t, pad=0.12):
        for l in self.lines:
            if l["start"] - 0.02 <= t < l["end"] + pad:
                return l
        return None

    def _blinks(self):
        self.blinks = {}
        for n in self.names:
            rng = np.random.default_rng(sum(map(ord, n)) * 7919)         # not hash(): that changes every run
            t, out = rng.uniform(0.8, 2.5), []
            while t < self.total:
                out.append(t)
                t += rng.uniform(2.3, 5.2)
            for l in self.lines:                         # a blink as each of their lines starts
                if l["speaker"] == n:
                    out.append(l["start"] + 0.05)
            self.blinks[n] = np.array(sorted(out))

    def eyes_at(self, who, t):
        i = np.searchsorted(self.blinks[who], t, side="right") - 1
        if i >= 0:
            u = t - self.blinks[who][i]
            if u < 3 / FPS:
                return (1, 2, 1)[int(u * FPS)]
        return 0

    def _envelopes(self, ep):
        """loudness of every take at the video frame rate, 0..1, to drive head nods"""
        self.env = {}
        for l in self.lines:
            x, sr = sf.read(ep / "build" / "tts" / l["file"], dtype="float32")
            hop = sr // FPS
            frames = x[: len(x) // hop * hop].reshape(-1, hop)
            e = np.sqrt((frames ** 2).mean(1))
            self.env[l["id"]] = np.clip(e / max(1e-6, np.percentile(e, 95)), 0, 1.3)

    def mouth_at(self, line, t):
        u = t - line["start"] + 0.03                    # the mouth leads the sound a hair
        for a, b, v in self.cues[line["id"]]:
            if a <= u < b:
                return v
        return "X"

    def char_state(self, who, t):
        x, bob, roll = self.x_at(who, t)
        sink, squash, frozen = self.pose_at(who, t)
        ph = sum(map(ord, who)) * 0.37
        cur = self.speaker_at(t)
        speaking = cur is not None and cur["speaker"] == who and t < cur["end"] + 0.02
        mouth, nod = "X", 0.6 * math.sin(2 * math.pi * 0.19 * t + ph)
        if speaking:
            mouth = self.mouth_at(cur, t)
            k = int((t - cur["start"]) * FPS)
            e = self.env[cur["id"]]
            level = float(e[min(k, len(e) - 1)])
            nod = (1.0 * math.sin(2 * math.pi * 1.35 * t + ph) + 0.8 * (level - 0.5)) * (0.5 + level)
        elif cur is not None and abs(t - cur["end"]) < 0.2 and cur["speaker"] == who:
            mouth = "A"
        # gaze: the speaker looks at who they are talking to, the rest at the speaker
        gaze = 0
        focus = cur or self._last_line(t)
        if focus is not None:
            target = self._addressee(focus) if focus["speaker"] == who else focus["speaker"]
            if target and target != who:
                dx = self.x_at(target, t)[0] - x
                gaze = 0 if abs(dx) < 140 else (1 if dx > 0 else -1)
        eyes = 0 if frozen else self.eyes_at(who, t)
        if frozen:
            mouth, nod, bob, roll = "X", 0.0, 0.0, 0.0
        breathe = 0.0 if frozen else 1.6 * math.sin(2 * math.pi * 0.23 * t + ph)
        return dict(who=who, x=x, y=self.floor + sink + bob + breathe, H=self.height[who], mouth=mouth, eyes=eyes, gaze=gaze,
                    nod=nod, roll=roll + (0.0 if frozen else 0.35 * math.sin(2 * math.pi * 0.17 * t + ph)), squash=squash)

    def _last_line(self, t):
        prev = [l for l in self.lines if l["end"] <= t]
        return prev[-1] if prev and t - prev[-1]["end"] < 1.2 else None

    def _addressee(self, line):
        i = self.lines.index(line)
        for j in (i + 1, i - 1):
            if 0 <= j < len(self.lines) and self.lines[j]["speaker"] != line["speaker"] and abs(self.lines[j]["start"] - line["start"]) < 6:
                return self.lines[j]["speaker"]
        return None

    # ------------------------------------------------------------------ props
    def _props(self):
        self.prop_cfg = self.stg["props"]
        self.holds = {}
        for k, p in self.prop_cfg.items():
            if "hold" in p:
                self.holds[k] = sorted([dict(h, t=self.T(h)) for h in p["hold"]], key=lambda h: h["t"])
        self.moves = {}
        for m in self.stg["bench_moves"] + self.stg["chair_moves"]:
            self.moves.setdefault(m["prop"], []).append(dict(m, t0=self.T(m)))
        for v in self.moves.values():
            v.sort(key=lambda m: m["t0"])
        self.swaps = {}
        for s in self.stg["swaps"]:
            self.swaps.setdefault(s["prop"], []).append(dict(s, t=self.T(s)))
        for v in self.swaps.values():
            v.sort(key=lambda s: s["t"])

    def prop_state(self, key, t, chars):
        """(sprite spec, x, y, z, crop) or None if not visible. sprite spec: (kind, args, kwargs)"""
        p = self.prop_cfg[key]
        args, kwargs, visible = tuple(p.get("args", ())), dict(p.get("kwargs", {})), True
        for s in self.swaps.get(key, []):
            if t >= s["t"]:
                if s.get("hide"):
                    visible = False
                if "args" in s:
                    args = tuple(s["args"])
                if "kwargs" in s:
                    kwargs = dict(s["kwargs"])
        if not visible:
            return None
        x, y = p["pos"]
        crop = None
        z = p["z"]
        if "appear" in p:
            t0 = self.T(p["appear"])
            if t < t0:
                return None
            if "reveal" in p:
                crop = ease((t - t0) / p["reveal"]["dur"])
        if "grow" in p:
            g = p["grow"]
            t0 = self.T(g)
            if t < t0:
                return None
            args = (g["to"] * ease((t - t0) / g["dur"]),)
            if args[0] < 2:
                return None
        for m in self.moves.get(key, []):
            if t >= m["t0"]:
                u = ease((t - m["t0"]) / m["dur"])
                x, y = lerp(x, m["to"][0], u), lerp(y, m["to"][1], u)
        if "follows" in p:
            f = p["follows"]
            t0, t1 = self.T(f["from"]), self.T(f["until"])
            if t < t0:
                return None
            x, y = self.x_at(f["who"], min(t, t1))[0] + f["dx"], self.floor + f["dy"]      # stays where it was left
        if key in self.holds:
            hs = [h for h in self.holds[key] if t >= h["t"]]
            if not hs:
                return None
            h = hs[-1]
            c = chars[h["who"]]
            lift = 0.0
            if key == "mug":                              # the sip
                t0 = self.items["D5.3"]["start"]
                if t0 + 0.5 <= t < t0 + 1.7:
                    lift = -0.2 * math.sin(math.pi * (t - t0 - 0.5) / 1.2)
            x = c["x"] + h["dx"] * c["H"]
            y = c["y"] + (h["dy"] + lift) * c["H"]
            z = "held"
        if "fall" in p:
            f = p["fall"]
            t0 = self.T(f)
            if t < t0:
                return None
            c = chars[f["who"]]
            u = ease((t - t0) / f["dur"])
            x = c["x"]
            y = c["y"] + lerp(-1.25, f["dy"], u) * c["H"]
        return dict(key=key, kind=p["kind"], args=args, kwargs=kwargs, x=x, y=y, z=z, crop=crop, scale=p.get("scale", 1.0))

    # ----------------------------------------------------------------- camera
    def _shots(self):
        self.shot_list = sorted([dict(s, t=self.items[s["from"]]["start"]) for s in self.shots["shots"]], key=lambda s: s["t"])
        for a, b in zip(self.shot_list, self.shot_list[1:] + [dict(t=self.tl["end_of_story"])]):
            a["t1"] = b["t"]
        self.inserts = sorted([dict(i, t0=self.T(i)) for i in self.shots["inserts"]], key=lambda i: i["t0"])
        for i in self.inserts:
            i["t1"] = i["t0"] + i["dur"]

    def _view_of(self, spec, t, chars, line):
        cam = spec["cam"]
        floor = self.floor
        if cam == "wide":
            return (PLATE[0] / 2, PLATE[1] / 2, float(PLATE[0]))
        if cam.startswith("single:"):
            who = cam.split(":")[1]
            c = chars[who]
            return (c["x"], floor - 0.60 * c["H"], 700.0)
        if cam.startswith("two:"):
            a, b = cam.split(":")[1].split("+")
            ca, cb = chars[a], chars[b]
            w = max(abs(ca["x"] - cb["x"]) + 640, 860.0)
            return ((ca["x"] + cb["x"]) / 2, floor - 0.55 * max(ca["H"], cb["H"]), w)
        if cam == "pan":
            p = ease((t - spec["t"]) / max(0.1, spec["t1"] - spec["t"]))
            a, b = spec["views"]
            return tuple(lerp(a[i], b[i], p) for i in range(3))
        raise ValueError(cam)

    def camera(self, t, chars):
        spec = self.shot_list[0]                         # the first shot also covers the room tone before it
        for s in self.shot_list:
            if s["t"] <= t:
                spec = s
        line = self.speaker_at(t, 0.0)
        cam = spec["cam"]
        # a speaker who is not in the shot gets a single of their own
        who = {"single": lambda c: [c.split(":")[1]], "two": lambda c: c.split(":")[1].split("+")}.get(cam.split(":")[0])
        if who and line is not None and line["speaker"] not in who(cam) and spec.get("auto", True):
            spec = dict(spec, cam=f"single:{line['speaker']}", push=0.0)
        cx, cy, w = self._view_of(spec, t, chars, line)
        if spec.get("push"):
            w *= 1 - spec["push"] * ease((t - spec["t"]) / max(0.1, spec["t1"] - spec["t"]))
        w = min(max(w, 380.0), float(PLATE[0]))
        h = w / FRAME_W
        cx = min(max(cx, w / 2), PLATE[0] - w / 2)
        cy = min(max(cy, h / 2), PLATE[1] - h / 2)
        return (cx, cy, w)

    # ------------------------------------------------------------------- frame
    def at(self, t):
        chars = {n: self.char_state(n, t) for n in self.names}
        props = [s for s in (self.prop_state(k, t, chars) for k in self.prop_cfg) if s]
        line = self.speaker_at(t, 0.1)
        insert = next((i["card"] for i in self.inserts if i["t0"] <= t < i["t1"]), None)
        ins_alpha = 1.0
        if insert:
            i = next(i for i in self.inserts if i["t0"] <= t < i["t1"])
            ins_alpha = min(1.0, (t - i["t0"]) / 0.1, (i["t1"] - t) / 0.1)
        title = None
        for n, sc in self.scenes.items():
            span = self.tl["scenes"][str(n)]
            if span["start"] <= t < span["start"] + 2.6:
                title = (f"SCENE {n}  —  {sc.title}", min(1.0, (t - span["start"]) / 0.3, (span["start"] + 2.6 - t) / 0.4))
        return dict(t=t, view=self.camera(t, chars), chars=chars, props=props, insert=insert, insert_alpha=ins_alpha,
                    caption=(line["speaker"], line["text"]) if line else None, title=title, end=t >= self.tl["end_of_story"])
