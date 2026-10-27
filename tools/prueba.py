"""ISO de prueba: agrega caracteres del español a todos los textos.

Sirve para comprobar en PCSX2 que la fuente y el motor los dibujan bien y que
los archivos que crecen se reubican sin romper nada.

  python tools/prueba.py [--disco 1]
  -> work/prueba_disco1.iso
"""
import argparse
import os

from textos import ROOT, SOURCES, apply, from_po, split_speaker, sbl_entries, sub_entries
from x2iso import Iso, Volume, build, iso_paths

SBL_PREFIX = "áéíóú ñ ¿¡ ÁÉÍÓÚÑ ü — "
SUB_PREFIX = "¿Sí? ¡Ñandú! "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disco", type=int, choices=(1, 2), default=1)
    args = ap.parse_args()
    iso_path = iso_paths()[args.disco - 1]
    iso = Iso(iso_path)
    replacements = {}
    for group, pattern, kind in SOURCES.values():
        for g in ([group] if group is not None else [iso.groups[-1]]):
            vol = Volume(iso, g)
            for e in vol.find(pattern):
                data = vol.read(e)
                if kind == "sbl":
                    table = {ctx: SBL_PREFIX + text for ctx, _, text in sbl_entries(data)}
                else:
                    table = {ctx: SUB_PREFIX + text for ctx, _, text in sub_entries(data)}
                new = apply(kind, data, table, {})
                if new is not None:
                    replacements[(g, e.path)] = new
    build(iso_path, os.path.join(ROOT, "work", f"prueba_disco{args.disco}.iso"), replacements)


if __name__ == "__main__":
    main()
