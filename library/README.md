# Library

Everything the episodes are built from. **[INDEX.md](INDEX.md) lists every character, background, prop and clip**
(generated; open that to find something).

```
library/
  characters/<id>/       one folder per character; the id is the full name in kebab-case (erling-haaland)
    character.yaml         name, short name, role, height, look, outfits, and a description of every reference sheet
    kit/<outfit>/          the puppet kit: front, three_quarter, side and hands sheets (.png), each with a .yaml
                           saying which drawing is which part
    reference/             everything else drawn for them: model sheets, outfit line-ups, expression and pose
                           sheets, older part atlases
  backgrounds/<setting>/ empty sets, by setting: stadiums, training-ground, club, tv-and-media, home, spa-and-pool,
                         pub-and-restaurant, nightlife, street, concert; indexed in backgrounds.yaml
  props/<set>/           cut-out props (transparent PNG); the uncut sheet is in the set's source/ folder
  extras/                background cast (crowds, crew): sheets that still need cutting up
  reference/             finished artwork kept for the look and staging, not used as animation assets
  audio/                 voiceovers/<character id>/, sfx/, music/ (see audio/README.md)
  fonts/
```

## Names

- **Characters**: the folder name is the id, used everywhere (scripts, voice files, the engine). Full name,
  lower case, hyphens: `gary-neville`, `gary-lineker`, `50-cent`. Two people with the same first name are never
  told apart by first name alone.
- **Outfits**: `home` (club or match kit), `casual`, `suit`, or a special one named for what it is (`concert`).
- **Views**: `front`, `three_quarter`, `side`, `hands` (plus `back` if a kit ever has one). Paired parts are
  anatomical: `_R` is the character's own right.
- **Backgrounds and props**: `<setting>/<what-it-is>.png`, lower case, hyphens, no "empty" or "backdrop" padding
  (every background is empty by definition). The id (`stadiums/old-trafford`) is the path without `.png`.
- **Reference sheets**: named for what they are (`model-sheet.png`, `outfits.png`, `concert-sheet.png`,
  `expressions-lip-sync.png`, `poses-<what>.png`, `parts-atlas*.png`).

## What state is everything in

- **Puppet kits (ready to rig):** 16 characters have all four sheets labelled part by part and checked by eye.
  Gary Neville, Roy Keane and Jamie Carragher are stand-ins in a different, thinner-outlined style
  (`style: provisional`) until their dark-outline kits arrive.
- **Reference only, no kit yet:** Carlos Baleba, Youri Tielemans, Andrey Santos (a front-view three-outfit atlas
  each) and 50 Cent (model sheets). They can be built from those sheets or given proper kits; they cannot be
  rigged as they stand.
- **Backgrounds:** 37 sets, all single flat images, 1672x941 at best (below 1080p). 16 of them are portrait
  (941x1672) and don't fill a 16:9 frame as they are. The index marks which. They carry no foreground layers, so
  anything a character should walk behind has to be cut out by hand.
- **Props:** the lunch set is cut out and ready. The concert extras are still a single reference sheet.

## Adding to the library

- **A character's kit:** `python3 tools/import_kit.py KIT.zip --outfit home`, then `python3 -m studio.ingest.kit
  label CHARACTER`, check `build/ingest/<id>_charts.jpg` by eye, fix with `swap` or the YAML, then
  `python3 -m studio.ingest.kit check CHARACTER` (one character at a time). Details are in the root README.
- **Other art for a character:** put it in `characters/<id>/reference/` and describe it in the `reference:` map
  of `character.yaml`.
- **A background:** `backgrounds/<setting>/<name>.png`, landscape 16:9 (1920x1080 or larger if you can), and an
  entry in `backgrounds.yaml`.
- **A prop:** cut out on transparent, `props/<set>/<name>.png`, with the uncut sheet kept in `source/` and an entry
  in `props.yaml`.
- **Then run `python3 tools/index_library.py --check`.** It rewrites INDEX.md and lists anything unfiled,
  undescribed or unchecked.

## Not here yet

The delivered packs did not contain the earlier 80-character, three-outfit, 96-background collection (the
files were lost before they were saved), so most of that wish list does not exist as art. The catalogue's
coverage notes list these people as having **no sheets at all**:

Lionel Messi, Casemiro, David Beckham, Eric Cantona, Alex Ferguson, Zlatan Ibrahimovic, Ronaldinho, Kylian Mbappe,
Mohamed Salah, Harry Kane, Jose Mourinho, Jurgen Klopp, Mikel Arteta, Marcus Rashford, Kobbie Mainoo, Lamine Yamal,
Jude Bellingham, Vinicius Junior, Bukayo Saka, Martin Odegaard, Declan Rice, William Saliba, Gabriel Magalhaes,
Kai Havertz, Gabriel Jesus, Thierry Henry, Dennis Bergkamp, Ian Wright, Arsene Wenger, Carlo Ancelotti, Neymar,
Robert Lewandowski, Ousmane Dembele, Raphinha, Pedri, Jamal Musiala, Florian Wirtz, Cole Palmer, Phil Foden, Rodri,
Kevin De Bruyne, Virgil van Dijk, Son Heung-min, Achraf Hakimi, Khvicha Kvaratskhelia, Alexander Isak,
Viktor Gyokeres, Thibaut Courtois, Gianluigi Donnarumma, Emiliano Martinez, Luis Enrique, Diego Simeone,
Xabi Alonso, Thomas Tuchel, Victor Osimhen, Sergio Ramos, Trent Alexander-Arnold, Gareth Southgate,
Aitana Bonmati, Alexia Putellas, Alessia Russo, Chloe Kelly, Sam Kerr, Jill Scott.

The full Manchester United squad is not covered either (Joshua Zirkzee, for one, has no sheet). The old party scenes
in `reference/party-scenes/` show a conga line of United managers (Moyes, Van Gaal, Mourinho, Solskjaer, Rangnick,
Ten Hag, Sir Alex) who only exist there as small figures; none of them has a sheet of their own.
