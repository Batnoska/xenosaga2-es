"""Parche de distribución: los archivos que cambia la traducción, para aplicarlos a la ISO de otro.

  python tools/parche.py crear work/xenosaga2_es.zip
      Compara las ISO traducidas de work/ con las originales (iso_path.txt) y guarda en un .zip
      las diferencias de cada archivo que cambió, con el SHA-1 del original y del resultado
      (manifest.json). Solo van las diferencias: el paquete no lleva archivos del juego.
  python tools/parche.py aplicar paquete.zip ISO_original ISO_nueva
      Reconoce el disco por el ejecutable, comprueba que cada archivo a reemplazar sea el
      original esperado (si no, no escribe nada) y arma la ISO traducida. Solo se tocan los
      archivos de la traducción: el resto (las voces, por ejemplo) queda como esté en esa ISO.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import zipfile

from x2iso import Iso, Volume, build, iso_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCS = {"SLUS_208.92": 1, "SLUS_211.33": 2}


def sha1(data):
    return hashlib.sha1(data).hexdigest()


# Diferencias entre un archivo original y el traducido: una lista de operaciones
#   0, u32 posición, u32 largo: copiar ese tramo del original
#   1, u32 largo, bytes:        agregar estos bytes
# Los tramos iguales de al menos BLOCK + STEP - 1 bytes se copian del original, aunque estén
# corridos, así que lo que se agrega es casi solo lo nuevo de la traducción.
BLOCK, STEP = 16, 4


def delta(src, dst):
    index = {}
    for i in range(0, len(src) - BLOCK + 1, STEP):
        index.setdefault(src[i:i + BLOCK], i)
    out, pending, i, n = bytearray(), 0, 0, len(dst)
    while i <= n - BLOCK:
        j = index.get(dst[i:i + BLOCK])
        if j is None:
            i += 1
            continue
        k = BLOCK
        while dst[i + k:i + k + 4096] == src[j + k:j + k + 4096] and i + k + 4096 <= n and j + k + 4096 <= len(src):
            k += 4096
        while i + k < n and j + k < len(src) and dst[i + k] == src[j + k]:
            k += 1
        while i > pending and j > 0 and dst[i - 1] == src[j - 1]:
            i, j, k = i - 1, j - 1, k + 1
        if i > pending:
            out += struct.pack("<BI", 1, i - pending) + dst[pending:i]
        out += struct.pack("<BII", 0, j, k)
        i = pending = i + k
    if pending < n:
        out += struct.pack("<BI", 1, n - pending) + dst[pending:]
    return bytes(out)


def undelta(src, ops):
    out, pos = bytearray(), 0
    while pos < len(ops):
        if ops[pos] == 0:
            start, length = struct.unpack_from("<II", ops, pos + 1)
            out += src[start:start + length]
            pos += 9
        else:
            length = struct.unpack_from("<I", ops, pos + 1)[0]
            out += ops[pos + 5:pos + 5 + length]
            pos += 5 + length
    return bytes(out)


def changed_files(original, translated):
    """[(grupo o "raiz", ruta, bytes originales, bytes nuevos)] de lo que difiere entre dos ISO."""
    out = []
    for g in original.groups:
        old, new = Volume(original, g), Volume(translated, g)
        for path, e in new.by_path.items():
            a, b = old.read(old.by_path[path]), new.read(e)
            if a != b:
                out.append((g, path, a, b))
    for name in original.files:
        if not name.startswith("XENOSAGA.") and name in translated.files:
            a, b = original.read_file(name), translated.read_file(name)
            if a != b:
                out.append(("raiz", name, a, b))
    return out


def create(package):
    manifest, deltas = {"discos": {}}, {}
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for disc, path in enumerate(iso_paths(), 1):
            original, translated = Iso(path), Iso(os.path.join(ROOT, "work", f"xenosaga2_es_disco{disc}.iso"))
            entries = []
            for g, name, a, b in changed_files(original, translated):
                key = (sha1(a), sha1(b))
                if key not in deltas:
                    d = delta(a, b)
                    assert undelta(a, d) == b, name
                    deltas[key] = f"{sha1(d)}.dif"
                    if deltas[key] not in z.namelist():
                        z.writestr(deltas[key], d)
                stored = deltas[key]
                entries.append({"grupo": g, "ruta": name, "original": sha1(a), "nuevo": sha1(b), "archivo": stored})
            manifest["discos"][original.executable] = entries
            print(f"disco {disc}: {len(entries)} archivos")
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        # La misma lista en texto plano, para el aplicador de Windows (tools/aplicador).
        z.writestr("manifest.tsv", "".join(
            "\t".join([exe, str(e["grupo"]), e["ruta"], e["original"], e["nuevo"], e["archivo"]]) + "\n"
            for exe, entries in manifest["discos"].items() for e in entries))
    print(f"{package}: {os.path.getsize(package) // 1024} KB")


def apply(package, iso_in, iso_out):
    iso = Iso(iso_in)
    with zipfile.ZipFile(package) as z:
        manifest = json.loads(z.read("manifest.json"))
        entries = manifest["discos"].get(iso.executable)
        if entries is None:
            sys.exit(f"{iso_in}: no es un disco de Xenosaga Episode II (NTSC-U): {iso.executable}")
        volumes = {g: Volume(iso, g) for g in iso.groups}
        replacements, loose, bad = {}, {}, []
        exe_traducido = False
        for e in entries:
            if e["grupo"] == "raiz":
                current = iso.read_file(e["ruta"])
            else:
                vol = volumes[e["grupo"]]
                current = vol.read(vol.by_path[e["ruta"]]) if e["ruta"] in vol.by_path else b""
            if e["grupo"] == "raiz" and e["ruta"] == iso.executable:
                exe_traducido = sha1(current) == e["nuevo"]
            if sha1(current) == e["nuevo"]:
                continue  # ya está traducido
            if sha1(current) != e["original"]:
                bad.append(e["ruta"])
                continue
            data = undelta(current, z.read(e["archivo"]))
            assert sha1(data) == e["nuevo"], f"paquete dañado: {e['archivo']}"
            if e["grupo"] == "raiz":
                loose[e["ruta"]] = data
            else:
                replacements[(e["grupo"], e["ruta"])] = data
    if bad and exe_traducido:
        # el ejecutable casi nunca cambia entre versiones de la traducción; los textos sí
        sys.exit(f"{iso_in}: tiene una versión anterior de la traducción. Aplica el parche sobre tu ISO original.")
    if bad:
        sys.exit("Estos archivos no son los originales esperados (¿otra versión del juego?):\n  "
                 + "\n  ".join(bad[:20]) + (f"\n  ... y {len(bad) - 20} más" if len(bad) > 20 else ""))
    print(f"disco {DISCS.get(iso.executable, '?')}: {len(replacements) + len(loose)} archivos para reemplazar")
    build(iso_in, iso_out, replacements, loose)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crear")
    c.add_argument("paquete")
    a = sub.add_parser("aplicar")
    a.add_argument("paquete")
    a.add_argument("iso_original")
    a.add_argument("iso_nueva")
    args = ap.parse_args()
    if args.cmd == "crear":
        create(args.paquete)
    else:
        apply(args.paquete, args.iso_original, args.iso_nueva)


if __name__ == "__main__":
    main()
