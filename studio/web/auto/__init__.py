"""The auto-director: the film/ package of an episode made in the web studio, worked out from its studio.json.

A web episode's own episodes/<slug>/film/*.py are one-line shims onto these modules, so the engine's CLI
(python3 -m studio.film SLUG timeline | sound | still | render ...) runs it like any other episode. To direct an
episode by hand (beats, inserts, props, foley), replace a shim with the module's own code and edit it.

studio.json:
    title, show, tagline, place          the title card and the opening caption ("" for none)
    background                           a library background id: "home/living-room"
    cast: [{id, drawing, x, floor, height, voice, caption, mood}]
        x, floor                         where they stand: fractions of the background's width and height
        height                           how tall they stand, as a fraction of the background's height
        voice                            {"kind": "tts", "voice": "bm_george", "speed": 1.0}
                                         or {"kind": "recording", "file": "01-<id>.wav"} (every line, in order)
        caption                          the lower third under their name (default: the role in character.yaml)
        mood                             their resting face: a delivery tag from studio/film/perf.py TAGS
    lines: [{id, who, to, text, tone, pause}]
        to                               who the line is said to: a cast id, "cam", or "" (worked out)
        tone                             a delivery tag (studio/film/perf.py TAGS), "" to guess from the text
        pause                            seconds of silence before the line ("" for the house pacing)"""
