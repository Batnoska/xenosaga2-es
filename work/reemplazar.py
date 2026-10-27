"""Arma un lote de borradores reemplazando textos en las traducciones existentes.

  python work/reemplazar.py pares.tsv work/borrador/fixNN.txt [carpeta ...]

pares.tsv: viejo<TAB>nuevo por línea (\\n para saltos). Cada par reemplaza ese texto donde
aparezca dentro de una traducción; si la línea empieza con "=", el par solo se aplica a
traducciones que son exactamente ese texto. Sin carpetas, revisa todas.
"""
import glob
import os
import sys

sys.path.insert(0, "tools")
import po
from x2text import width

sys.stdout.reconfigure(encoding="utf-8")
pairs_path, out_path, *folders = sys.argv[1:]
pairs = []
for line in open(pairs_path, encoding="utf-8"):
    line = line.rstrip("\n")
    if line.strip():
        whole = line.startswith("=")
        old, new = line.lstrip("=").split("\t")
        pairs.append((whole, old.replace("\\n", "\n"), new.replace("\\n", "\n")))
used = [0] * len(pairs)
out = []
for path in sorted(glob.glob("traduccion/*/*.po")):
    name = os.path.relpath(path, "traduccion")[:-3].replace(os.sep, "/")
    if folders and name.split("/")[0] not in folders:
        continue
    lines = []
    for e in po.read(path)[1]:
        new = e.msgstr
        for i, (whole, old, rep) in enumerate(pairs):
            after = (rep if new == old else new) if whole else new.replace(old, rep)
            used[i] += after != new
            new = after
        if new != e.msgstr:
            print(f"{name} {e.msgctxt}: {max(width(l) for l in new.split(chr(10)))} {new.replace(chr(10), ' / ')[:110]}")
            lines.append(f"{e.msgctxt}\t{new.replace(chr(10), chr(92) + 'n')}")
    if lines:
        out += [f"=== {name}"] + lines
for (whole, old, _), n in zip(pairs, used):
    if not n:
        print("SIN USO:", old)
open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"{sum(1 for l in out if not l.startswith('==='))} entradas en {out_path}")
