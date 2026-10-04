"""The soundtrack for the test: the actors' lines with a little of the studio round them, the studio's room tone,
the foley the picture asks for (Micah turning the reader over, the door, Pep's steps, the phone's tap and the
reader's beep), and the title boom with its chord. Every cue hangs off the same marks as the shots and the acting.
python3 -m studio.film the-appeals-department sound -> build/episode_audio.wav"""
import json

from studio.film import audio as A
from studio.film import ep
from studio.film.shots import Marks
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le = T.m, T.ls, T.le


def ambience(bus):
    # the studio: air-conditioning and nothing else; it stops dead on the cut to the title
    A.bed(bus, "ambience/room-tone-hvac", 0.0, m("cut_title"), -54, lowpass=3800, fin=0.05)


def foley(bus):
    # the sales team: Micah settles in his chair as the two-shot starts
    A.ev(bus, "cloth/cloth-c", m("cut_gm1") + 0.35, -46, pan=0.25)
    A.ev(bus, "creaks/creak-small", m("cut_gm1") + 0.5, -50, pan=0.25, semis=-2)
    # Micah turns the card reader over (the turn is 0.55-0.75 s into the insert): his sleeve, the plastic
    A.ev(bus, "cloth/cloth-e", m("cut_reader1") + 0.45, -42)
    A.ev(bus, "foley/pen-click-c", m("cut_reader1") + 0.68, -40, semis=-7, lowpass=4000)
    # a quiet door squeak off to the right; heads turn (a jacket, a chair)
    A.ev(bus, "creaks/creak-short", m("squeak"), -40, pan=0.75, semis=3, highpass=500)
    A.ev(bus, "cloth/cloth-a", m("squeak") + 0.18, -46, pan=-0.2)
    A.ev(bus, "creaks/creak-small", m("squeak") + 0.3, -50, pan=0.1, semis=-3)
    # Pep comes in, off right: two steps on the studio floor and he is behind the guest chair
    A.steps(bus, m("squeak") + 0.45, m("cut_pep1") - 0.05, -42, pace=0.3, pan=0.8, pan_to=0.55, lowpass=5000)
    # the look: nobody moves, but a chair gives
    A.ev(bus, "creaks/creak-small", m("cut_look") + 0.4, -50, pan=-0.15, semis=-1)
    # Pep's phone: his sleeve as it comes in, the tap on the reader, the beep
    A.ev(bus, "cloth/cloth-f", m("tap") - 0.6, -46, pan=0.3)
    A.ev(bus, "foley/pen-click-a", m("tap"), -36, semis=-6, lowpass=3500)
    bus.add(A.at_level(A.room(A.beep(2700, 0.17), 0.3, 0.12), -31), m("tap") + 0.03)
    # the title: the big boom
    bus.add(A.at_level(A.big_boom(1.0), -16), m("cut_title"))


def music(bus):
    # the chord under the title boom, to the end
    n = TL["total"] - m("cut_title")
    y = A.title_sting(n + 0.2)[:int(n * A.SR)]
    y *= A.fade(len(y), 0.0, 0.8)[:, None]
    bus.add(A.at_level(y, -27), m("cut_title"))


def main():
    dlg, amb, fx, mus = A.Bus(), A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg, room_s=0.3, room_db=-24)
    ambience(amb)
    foley(fx)
    music(mus)
    A.master(dlg, [amb, fx], [mus])
