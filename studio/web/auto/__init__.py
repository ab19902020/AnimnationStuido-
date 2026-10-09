"""The auto-director: the film/ package of an episode made in the web studio, worked out from its studio.json.

A web episode's own episodes/<slug>/film/*.py are one-line shims onto these modules, so the engine's CLI
(python3 -m studio.film SLUG timeline | sound | still | render ...) runs it like any other episode. To direct an
episode by hand (beats, inserts, props, foley), replace a shim with the module's own code and edit it.

studio.json:
    title, show, tagline                 the title card ("" for none)
    scenes: [{name, background, place, stage}]
        background                       a library background id: "home/living-room"
        place                            the caption over the scene's opening wide ("" for none)
        stage                            {id: {x, floor, height}}: who is in the scene and where they stand, as
                                         fractions of the background's width and height (feet at x, floor)
    cast: [{id, drawing, voice, caption, mood}]
        voice                            {"kind": "tts", "voice": "bm_george", "speed": 1.0}
                                         or {"kind": "recording", "files": ["01-<id>.wav", ...]} (their lines, in
                                         order; one file or several)
        caption                          the lower third under their name (default: the role in character.yaml)
        mood                             their resting face: a delivery tag from studio/film/perf.py TAGS
    lines: [{id, scene, who, to, text, tone, pause}]
        to                               who the line is said to: a cast id, "cam", or "" (worked out)
        tone                             a delivery tag (studio/film/perf.py TAGS), "" to guess from the text
        pause                            seconds of silence before the line ("" for the house pacing)
"""


def normalize(sp):
    """an older one-set studio.json (background, cast with x/floor/height, lines) as scenes: every episode is
    scenes: [{name, background, place, stage: {id: {x, floor, height}}}], lines carry their scene's index"""
    sp = dict(sp)
    if not sp.get("scenes"):
        stage = {c["id"]: {k: c[k] for k in ("x", "floor", "height") if k in c} for c in sp.get("cast", [])}
        sp["scenes"] = [dict(name="", background=sp.get("background", ""), place=sp.get("place", ""), stage=stage)]
    for c in sp.get("cast", []):
        for k in ("x", "floor", "height"):
            c.pop(k, None)
    sp.pop("background", None)
    sp.pop("place", None)
    n = len(sp["scenes"])
    for ln in sp.get("lines", []):
        ln["scene"] = min(max(0, int(ln.get("scene") or 0)), n - 1)
    return sp
