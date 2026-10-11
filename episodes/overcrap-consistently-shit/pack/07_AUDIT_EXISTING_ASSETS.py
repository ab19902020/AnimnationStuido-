#!/usr/bin/env python3
"""Audit the original character sources in an existing local Passmic checkout.
Run: python path/to/07_AUDIT_EXISTING_ASSETS.py /path/to/Passmic
Does not alter files.
"""
from pathlib import Path
import json,sys
repo=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
paths=[
 'series/ep01/sheets/mark.png', 'series/ep01/sheets/gary.png',
 'series/ep01/sheets/layout.json','series/ep01/characters/mark/rig.json',
 'series/ep01/characters/gary/rig.json', 'series/ep01/episode.py',
 'series/ep01/README.md', 'tools/ep/epengine.py','tools/ep/render.py',
 'series/ep01/backgrounds/front_a.json','series/ep01/backgrounds/wide.json',
 'series/ep01/backgrounds/reverse.json'
]
missing=[]
for s in paths:
 f=repo/s
 print(('OK     ' if f.is_file() else 'MISSING'),s)
 if not f.is_file():missing.append(s)
if (repo/'series/ep01/sheets/layout.json').is_file():
 data=json.loads((repo/'series/ep01/sheets/layout.json').read_text())
 for person in ('mark','gary'):
  panels={p['panel'] for p in data[person]['bands']}
  print(person,'panels:',', '.join(sorted(panels)))
  if not {'mouths','expressions','upper','head','body'}.issubset(panels):
   print('WARNING missing expected panel types',person)
print('COMPLETE' if not missing else f'{len(missing)} source files missing; check working branch.')
sys.exit(bool(missing))
