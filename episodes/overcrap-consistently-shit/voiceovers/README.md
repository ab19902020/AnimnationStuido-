# Voiceovers: Consistently Shit

The actors' recordings as delivered (MP3, cloned voices), each reading his lines in script order. `film/lines.py` lists
them, and `python3 -m studio.film overcrap-consistently-shit lines` finds every line in them and cuts it.

| File | Voice | Lines | Length |
|---|---|---|---|
| `01-mark-goldbridge.mp3` | Mark Goldbridge | L001, L004, L005 | 12.9 s |
| `02-gary-neville.mp3` | Gary Neville | L002, L003, L006, L007 | 9.9 s |

All seven lines are read as scripted (Whisper hears "Manchester United had ever seen" for "I'd ever seen" in L002).
