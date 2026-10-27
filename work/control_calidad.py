"""Control de calidad de las traducciones: problemas típicos que se pueden detectar sin leer todo.

  python work/control_calidad.py            resumen por tipo de problema
  python work/control_calidad.py <tipo>     las entradas de ese tipo
"""
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import po

sys.stdout.reconfigure(encoding="utf-8")
CODES = re.compile(r"\$[^;]*;|<[^<>]{1,2}>|&\d\d|●|@")

# términos del glosario escritos de otra forma
VARIANTS = {
    "Industrias Vector": "Vector Industries", "Kukai Foundation": "Fundación Kukai", "Second Miltia": "Segunda Miltia",
    "Realianos": "Realians", "Realiano": "Realian", "Realianas": "Realians", "Realiana": "Realian",
    "Flota Inmigrante": "Flota de Inmigrantes", "Old Miltia": "Antigua Miltia",
    "Campaña GS": "Campaña SG", "GS Path": "Ruta SG", "Segment File": "Archivo de Segmento",
    "Segment Address": "Dirección de Segmento", "Archivo de Segmentos": "Archivo de Segmento",
    "Encephalon": "Encéfalo", "Kos-Mos": "KOS-MOS", "Kosmos": "KOS-MOS", "Momo": "MOMO",
    "Chaos": "chaos", "UMN": "U.M.N.", "Agente civil": "Agente Civil",
}
# palabras inglesas que casi nunca aparecen en un texto en español
ENGLISH = re.compile(r"\b(the|and|you|your|with|what|this|that|have|there|they|from|would|should|could|please|yes|okay)\b")


def entries():
    for path in sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "traduccion", "*", "*.po"))):
        folder = os.path.basename(os.path.dirname(path))
        for e in po.read(path)[1]:
            if e.msgstr:
                yield f"{folder}/{os.path.basename(path)[:-3]}", e


def problems(e):
    s = CODES.sub("X", e.msgstr)  # un marcador: los botones ocupan lugar
    found = []
    for open_, close in (("¡", "!"), ("¿", "?")):
        depth = 0
        for ch in s:
            depth += (ch == open_) - (ch == close)
            if depth < 0:
                found.append(f"{close} sin {open_}")
                break
        else:
            if depth > 0:
                found.append(f"{open_} sin {close}")
    if re.search(r"(?<=\S)  +(?=\S)", s):
        found.append("espacio doble")
    if re.search(r" [,.;:!?](?!\.)", s) and not re.search(r" \.\.\.", s):
        found.append("espacio antes de puntuación")
    if re.search(r"[,;](?=[A-Za-zÁÉÍÓÚáéíóúÑñ])", s):
        found.append("falta espacio después de , o ;")
    if re.search(r"(?<![\w.])\.\.(?!\.)", s):
        found.append("dos puntos seguidos (..)")
    words = set(ENGLISH.findall(s.lower()))
    if words:
        found.append("inglés: " + ", ".join(sorted(words)))
    for bad, good in VARIANTS.items():
        if re.search(rf"\b{re.escape(bad)}\b", s):
            found.append(f"«{bad}» → «{good}»")
    if e.msgid.rstrip().endswith(("?", "!", ".")) and s and s.rstrip()[-1:] not in "?!.…»\"'):♪" and "\n" not in e.msgid:
        found.append("sin puntuación final")
    return found


def main():
    by_kind = defaultdict(list)
    for where, e in entries():
        for p in problems(e):
            kind = p.split(":")[0] if p.startswith("inglés") else p if not p.startswith("«") else "glosario"
            by_kind[kind].append((where, e, p))
    if len(sys.argv) > 1:
        for where, e, p in by_kind.get(" ".join(sys.argv[1:]), []):
            print(f"== {where} {e.msgctxt}  [{p}]")
            print("   EN:", e.msgid.replace("\n", " / "))
            print("   ES:", e.msgstr.replace("\n", " / "))
        return
    for kind, items in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(items):5}  {kind}")


if __name__ == "__main__":
    main()
