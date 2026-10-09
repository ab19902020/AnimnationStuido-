"""A web episode's mix: the dialogue with a little of the room, under each scene a recorded ambience bed chosen by
the kind of set, and the title boom with its chord. python3 -m studio.film SLUG sound -> build/episode_audio.wav
(-16 LUFS)"""
from studio.film import audio as A
from studio.web.auto import spec as S
from studio.web.auto.timeline import TL

# the room each kind of set sounds like: (ambience clip, level dB, low-pass Hz)
BEDS = {"street": ("ambience/street-distant", -46, 6000), "stadiums": ("crowd/crowd-large", -44, 5000),
        "training-ground": ("ambience/wind", -50, 3000), "spa-and-pool": ("ambience/sea-gentle", -50, 5000),
        "concert": ("crowd/crowd-large", -46, 4000), "nightlife": ("ambience/city-through-window", -48, 3000),
        "pub-and-restaurant": ("ambience/room-tone-hvac", -50, 4000)}
ROOM = ("ambience/room-tone-hvac", -54, 3800)


def main():
    dlg, amb, fx, mus = A.Bus(), A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg, room_s=0.3, room_db=-24)
    end = TL["marks"].get("cut_title", TL["total"])
    starts = [0.0] + [TL["marks"][f"scene_{k}"] for k in range(1, len(S.SCENES)) if f"scene_{k}" in TL["marks"]]
    ks = [0] + [k for k in range(1, len(S.SCENES)) if f"scene_{k}" in TL["marks"]]
    for j, k in enumerate(ks):                 # each scene's room, hard cut at the scene change
        a, b = starts[j], starts[j + 1] if j + 1 < len(starts) else end
        clip, level, lp = BEDS.get(S.SCENES[k]["background"].split("/")[0], ROOM)
        A.bed(amb, clip, a, b, level, lowpass=lp, fin=0.6 if j == 0 else 0.004, fout=0.05)
    if "cut_title" in TL["marks"]:
        t = TL["marks"]["cut_title"]
        fx.add(A.at_level(A.big_boom(1.0), -16), t)
        n = TL["total"] - t
        y = A.title_sting(n + 0.2)[:int(n * A.SR)]
        y *= A.fade(len(y), 0.0, 0.8)[:, None]
        mus.add(A.at_level(y, -27), t)
    A.master(dlg, [amb, fx], [mus])
