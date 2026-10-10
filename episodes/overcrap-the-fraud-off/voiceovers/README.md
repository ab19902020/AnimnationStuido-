# Voiceovers: The Fraud Off

The actors' recordings as delivered (MP3, cloned voices, one file per actor reading his lines in script order).
`film/lines.py` lists them, and `python3 -m studio.film overcrap-the-fraud-off lines` finds every line in them and
cuts it.

| File | Voice | Lines | Length |
|---|---|---|---|
| `01-jamie-carragher.mp3` | Jamie Carragher | a laugh, then L001, L003, L005, L007 | 13.6 s |
| `02-mark-goldbridge.mp3` | Mark Goldbridge | L002, L004, L006 (run together), L008 | 18.1 s |

Readings that differ from the pack's 30-second edit (`script.md` holds the words as recorded):

- Jamie opens with a laugh (0.1-0.8 s); it plays under the opening two-shot (`film/sound.py`).
- Jamie, L001: "First show" comes out close to "Fair shout", and "You're a Forest fan, Mark!" is mumbled: Whisper
  hears it as "You do not have a photo for a mark". The words are force-aligned as scripted.
- Jamie, L005: "me real name" for "my real name".
- Jamie, L007: "FRAUD!" is a long, stretched shout ("Froooots!" to Whisper; `HEARD` in `film/lines.py` places it).
- Mark, L002: "That's rich coming from... who spent his whole life..." for "That's rich from... who's spent his
  life...".
- Mark, L006: adds "Oh, here we go." and reads "You supported Everton, played for Liverpool and now work for a Man
  United legend! You'll support anyone who gives you a payslip!" for "Everton fan, Liverpool player, now working for
  a United legend! You'll support anyone with a payslip!".
