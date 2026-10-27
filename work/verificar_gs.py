"""Aplica las traducciones del GS Path y comprueba que el juego lea exactamente lo traducido."""
import os
import sys
sys.path.insert(0, 'tools')
sys.stdout.reconfigure(encoding='utf-8')
import textos
from x2text import GsText, decode

translations, names, problems = textos.load(False)
bad = 0
for (group, src), (kind, table) in translations.items():
    if kind != 'gs':
        continue
    data = open(os.path.join('work/extract/0', src), 'rb').read()
    new = GsText(textos.apply(kind, data, table, names))
    for k, (n, key, _, _) in enumerate(new.values):
        ctx = f'No.{n}/{key}'
        got = new.text(k)
        size = textos.gs_field(src, ctx)[0]
        if len(got) > size:
            print('NO ENTRA', src, ctx, len(got), size); bad += 1
        if ctx in table and decode(got, engine=True).replace('\xa0', ' ').strip() != table[ctx].strip():
            print('DISTINTO', src, ctx, repr(decode(got, engine=True))[:80]); bad += 1
    print(src, len(new.values), 'valores,', len(table), 'traducidos')
print('problemas:', bad, '| errores de control:', sum(p.startswith('ERROR') and 'gspath' in p for p in problems))
