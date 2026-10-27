"""Ayuda para cargar borradores de traducción en los .po.

  python tools/borrador.py ver traduccion/videos/s010100.po
      Lista las entradas sin traducir: msgctxt<TAB>[quién habla o tiempo]<TAB>texto
      (saltos de línea como \\n).
  python tools/borrador.py aplicar traduccion/videos/s010100.po borrador.tsv
      Carga un TSV msgctxt<TAB>traducción (saltos como \\n) como borrador (fuzzy).
  python tools/borrador.py memoria
      Copia como borrador la traducción de los textos idénticos ya traducidos en otro .po.
"""
import glob
import os
import sys

import po

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def context(entry):
    for c in entry.comments:
        if c.startswith(("habla: ", "tiempo ")):
            return c.split(" ", 1)[1]
    return ""


def show(path):
    _, entries = po.read(path)
    for e in entries:
        if not e.msgstr:
            print(f"{e.msgctxt}\t{context(e)}\t{e.msgid.replace(chr(10), chr(92) + 'n')}")


def apply(path, tsv):
    header, entries = po.read(path)
    drafts = {}
    for line in open(tsv, encoding="utf-8"):
        line = line.rstrip("\n")
        if line:
            key, text = line.split("\t", 1)
            drafts[key] = text.replace("\\n", "\n")
    by_key = {e.msgctxt: e for e in entries}
    missing = [k for k in drafts if k not in by_key]
    if missing:
        raise SystemExit(f"claves que no existen en {path}: {missing}")
    if os.path.basename(os.path.dirname(path)) == "gspath":
        # campos de recuadro fijo: lo que viene de corrido se parte al ancho del recuadro
        import textos
        from x2text import wrap
        source = header["X-Xeno-Source"].split(":", 1)[1]
        for key, text in drafts.items():
            _, px, lines = textos.gs_field(source, key)
            if "\n" not in text and lines > 1:
                drafts[key] = wrap(text, px)
    for key, text in drafts.items():
        by_key[key].msgstr, by_key[key].fuzzy = text, True
    po.write(path, header, entries)
    pending = sum(1 for e in entries if not e.msgstr)
    print(f"{len(drafts)} borradores cargados en {path} ({pending} sin traducir)")


def batch(path):
    """Archivo con varias secciones "=== carpeta/nombre" seguidas de líneas msgctxt<TAB>texto."""
    sections, current = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("=== "):
            current = line[4:].strip()
            sections.setdefault(current, [])  # el mismo archivo puede aparecer en varias secciones
        elif line.strip() and current:
            sections[current].append(line)
    tmp = path + ".tmp"
    for name, lines in sections.items():
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        apply(os.path.join(ROOT, "traduccion", name + ".po"), tmp)
    os.remove(tmp)


def review(folder):
    """Muestra los problemas (errores y avisos) de las traducciones de una carpeta de .po."""
    import textos
    from x2text import width
    kind = {"videos": "sub", "menus": "txd", "datos": "bat", "fijos": "fijo", "gspath": "gs"}.get(folder, "sbl")
    if kind == "sub":
        width = len  # los subtítulos se miden en caracteres; el resto, en píxeles
    for path in sorted(glob.glob(os.path.join(ROOT, "traduccion", folder, "*.po"))):
        header, entries = po.read(path)
        cutscene = header.get("X-Xeno-Tipo") == "cinematica"
        source = header["X-Xeno-Source"].split(":", 1)[1]
        for e in entries:
            if not e.msgstr:
                continue
            field = textos.gs_field(source, e.msgctxt) if kind == "gs" else None
            errors, warnings = textos.check(e.msgid, e.msgstr, kind, cutscene, e.msgctxt, field)
            if errors or warnings:
                widest = max(width(line) for line in e.msgid.split("\n"))
                print(f"== {os.path.basename(path)} {e.msgctxt}: {'; '.join(errors + warnings)} "
                      f"(original: {e.msgid.count(chr(10)) + 1} líneas, {widest} de ancho)")
                for line in e.msgstr.split("\n"):
                    print(f"  {width(line):3} {line}")


def memory():
    files = sorted(glob.glob(os.path.join(ROOT, "traduccion", "*", "*.po")))
    known = {}
    for path in files:
        for e in po.read(path)[1]:
            if e.msgstr and (e.msgid not in known or not e.fuzzy):
                known[e.msgid] = e.msgstr
    filled = 0
    for path in files:
        header, entries = po.read(path)
        changed = False
        for e in entries:
            if not e.msgstr and e.msgid in known:
                e.msgstr, e.fuzzy, changed = known[e.msgid], True, True
                filled += 1
        if changed:
            po.write(path, header, entries)
    print(f"{filled} textos repetidos completados")


if __name__ == "__main__":
    {"ver": lambda: show(sys.argv[2]), "aplicar": lambda: apply(sys.argv[2], sys.argv[3]),
     "lote": lambda: batch(sys.argv[2]), "revisar": lambda: review(sys.argv[2]), "memoria": memory}[sys.argv[1]]()
