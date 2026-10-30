"""Parche de distribución: los archivos que cambia la traducción, para aplicarlos a la ISO de otro.

  python tools/parche.py crear work/xenosaga2_es.zip
      Compara las ISO traducidas de work/ con las originales (iso_path.txt) y guarda en un .zip
      las diferencias de cada archivo que cambió, con el SHA-1 del original y del resultado
      (manifest.json). Solo van las diferencias: el paquete no lleva archivos del juego.
      Si está el repositorio de la Definitive Edition junto a este (o en X2_DEFINITIVA), agrega
      sus opciones y cambios (de.tsv).
  python tools/parche.py aplicar paquete.zip ISO_original ISO_nueva [--sin-traduccion]
                                 [--perfil definitiva] [--opcion vida_jefes=1 ...]
      Reconoce el disco por el ejecutable, comprueba que cada archivo a reemplazar sea el
      original esperado (si no, no escribe nada) y arma la ISO traducida. Solo se tocan los
      archivos de la traducción: el resto (las voces, por ejemplo) queda como esté en esa ISO.
      Con --perfil u --opcion aplica además la Definitive Edition; con --sin-traduccion, solo
      la Definitive Edition.
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
BATDAT = "yamamoto/batdat.us"


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


# Los subtítulos de los videos (movie/en/*.txt) van enteros y se aplican sobre cualquier original:
# la traducción los reescribe completos, y no todos los undub que circulan traen los mismos (en
# otra versión del disco 2 cambia s040110.txt). En el manifiesto, su "original" es CUALQUIERA.
CUALQUIERA = "*"


def entero(ruta):
    return ruta.startswith("movie/") and ruta.endswith(".txt")


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


def definitiva_tsv():
    """Las opciones, los perfiles y los cambios de la Definitive Edition en texto plano (de.tsv), si
    está su repositorio. Una línea por registro, con los campos separados por tabuladores:
      grupo   id  español  inglés
      opcion  id  grupo  probada  nombre (es, en)  descripción (es, en)
      nivel   opción  n  etiqueta (es, en)
      perfil  id  nombre (es, en)  descripción (es, en)  opción=nivel,...
      cambio  opción  nivel  batdat|exe  sección  posición  ancho  original  nuevo
    """
    carpeta = os.environ.get("X2_DEFINITIVA", os.path.join(os.path.dirname(ROOT), "Xenosaga2-DE"))
    if not os.path.exists(os.path.join(carpeta, "tools", "opciones.py")):
        return None
    sys.path.insert(0, os.path.join(carpeta, "tools"))
    import juego
    import opciones
    datos, filas = juego.Datos(), []
    for id_, g in opciones.GRUPOS.items():
        filas.append(["grupo", id_, g["es"], g["en"]])
    for o in opciones.OPCIONES:
        filas.append(["opcion", o.id, o.grupo, str(int(o.probada)), o.nombre["es"], o.nombre["en"],
                      o.descripcion["es"], o.descripcion["en"]])
        for n, etiqueta in enumerate(o.niveles, 1):
            filas.append(["nivel", o.id, str(n), etiqueta["es"], etiqueta["en"]])
        for n in range(1, max(1, len(o.niveles)) + 1):
            for c in o.cambios(datos, n):
                archivo = "exe" if c.seccion < 0 else "batdat"
                filas.append(["cambio", o.id, str(n), archivo] + [str(v) for v in c[1:]])
    for p in opciones.PERFILES:
        filas.append(["perfil", p.id, p.nombre["es"], p.nombre["en"], p.descripcion["es"], p.descripcion["en"],
                      ",".join(f"{k}={v}" for k, v in p.niveles.items())])
    assert not any("\t" in f or "\n" in f for fila in filas for f in fila)
    return "".join("\t".join(fila) + "\n" for fila in filas)


def leer_de(z):
    """{"opciones": [id...], "perfiles": {id: {opción: nivel}}, "cambios": {(opción, nivel): [...]}}
    del paquete, o None si no trae la Definitive Edition."""
    if "de.tsv" not in z.namelist():
        return None
    de = {"opciones": [], "perfiles": {}, "cambios": {}}
    for linea in z.read("de.tsv").decode("utf-8").splitlines():
        c = linea.split("\t")
        if c[0] == "opcion":
            de["opciones"].append(c[1])
        elif c[0] == "perfil":
            de["perfiles"][c[1]] = {k: int(v) for k, v in (p.split("=") for p in c[6].split(",") if p)}
        elif c[0] == "cambio":
            de["cambios"].setdefault((c[1], int(c[2])), []).append((c[3],) + tuple(int(v) for v in c[4:9]))
    return de


def aplicar_de(cambios, batdat, exe):
    """Escribe los cambios en batdat.us y el ejecutable (bytearray), comprobando cada valor original.
    En batdat.us la posición es relativa a la sección, cuyo inicio se lee del propio archivo."""
    n = struct.unpack_from("<I", batdat, 0)[0]
    inicios = struct.unpack_from(f"<{n}I", batdat, 8)
    for archivo, seccion, pos, ancho, original, nuevo in cambios:
        datos, p = (exe, pos) if archivo == "exe" else (batdat, inicios[seccion] + pos)
        if int.from_bytes(datos[p:p + ancho], "little") != original:
            raise ValueError(f"los datos de la Definitive Edition no coinciden ({archivo} {seccion} +{pos:#x})")
        datos[p:p + ancho] = nuevo.to_bytes(ancho, "little")


def create(package):
    manifest, deltas = {"discos": {}}, {}
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for disc, path in enumerate(iso_paths(), 1):
            original, translated = Iso(path), Iso(os.path.join(ROOT, "work", f"xenosaga2_es_disco{disc}.iso"))
            entries = []
            for g, name, a, b in changed_files(original, translated):
                if entero(name):
                    a = b""  # todo el archivo nuevo, sin copiar nada del original
                key = (sha1(a), sha1(b))
                if key not in deltas:
                    d = delta(a, b)
                    assert undelta(a, d) == b, name
                    deltas[key] = f"{sha1(d)}.dif"
                    if deltas[key] not in z.namelist():
                        z.writestr(deltas[key], d)
                stored = deltas[key]
                entries.append({"grupo": g, "ruta": name, "original": CUALQUIERA if entero(name) else sha1(a),
                                "nuevo": sha1(b), "archivo": stored})
            manifest["discos"][original.executable] = entries
            print(f"disco {disc}: {len(entries)} archivos")
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        # La misma lista en texto plano, para el aplicador de Windows (tools/aplicador).
        z.writestr("manifest.tsv", "".join(
            "\t".join([exe, str(e["grupo"]), e["ruta"], e["original"], e["nuevo"], e["archivo"]]) + "\n"
            for exe, entries in manifest["discos"].items() for e in entries))
        de = definitiva_tsv()
        if de:
            z.writestr("de.tsv", de)
            print(f"Definitive Edition: {de.count(chr(10) + 'cambio')} cambios")
        else:
            print("ojo: no está el repositorio de la Definitive Edition: el paquete va sin ella")
    print(f"{package}: {os.path.getsize(package) // 1024} KB")


def apply(package, iso_in, iso_out, traduccion=True, niveles=None):
    """Arma iso_out a partir de iso_in: con la traducción (si traduccion) y con la Definitive
    Edition en los niveles pedidos ({opción: nivel}). Partiendo de una ISO ya traducida, se puede
    agregar solo la Definitive Edition."""
    iso = Iso(iso_in)
    with zipfile.ZipFile(package) as z:
        manifest = json.loads(z.read("manifest.json"))
        entries = manifest["discos"].get(iso.executable)
        if entries is None:
            sys.exit(f"{iso_in}: no es un disco de Xenosaga Episode II (NTSC-U): {iso.executable}")
        de = leer_de(z)
        if niveles and de is None:
            sys.exit("este paquete no trae la Definitive Edition")
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
            if e["original"] not in (CUALQUIERA, sha1(current)):
                bad.append(e["ruta"])
                continue
            if not traduccion:
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
    cambios = [c for o in (de["opciones"] if de else []) if (niveles or {}).get(o)
               for c in de["cambios"][(o, niveles[o])]]
    if cambios:
        vol = volumes[0]
        batdat = bytearray(replacements.get((0, BATDAT)) or vol.read(vol.by_path[BATDAT]))
        exe = bytearray(loose.get(iso.executable) or iso.read_file(iso.executable))
        aplicar_de(cambios, batdat, exe)
        replacements[(0, BATDAT)], loose[iso.executable] = bytes(batdat), bytes(exe)
    if not replacements and not loose:
        sys.exit(f"{iso_in}: no hay nada que cambiar (ya tiene la traducción)")
    print(f"disco {DISCS.get(iso.executable, '?')}: {len(replacements) + len(loose)} archivos para reemplazar"
          + (f", {len(cambios)} cambios de la Definitive Edition" if cambios else ""))
    build(iso_in, iso_out, replacements, loose)


def niveles_pedidos(package, perfil, opciones):
    """{opción: nivel} a partir de un perfil y de ajustes "opción=nivel"."""
    if not perfil and not opciones:
        return {}
    with zipfile.ZipFile(package) as z:
        de = leer_de(z)
    if de is None:
        sys.exit("este paquete no trae la Definitive Edition")
    if perfil and perfil not in de["perfiles"]:
        sys.exit(f"perfil desconocido: {perfil} (hay {', '.join(de['perfiles'])})")
    niveles = dict(de["perfiles"][perfil]) if perfil else {}
    for a in opciones:
        k, v = a.split("=")
        if k not in de["opciones"] or (k, int(v)) not in de["cambios"] and int(v):
            sys.exit(f"opción o nivel desconocido: {a}")
        niveles[k] = int(v)
    return niveles


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crear")
    c.add_argument("paquete")
    a = sub.add_parser("aplicar")
    a.add_argument("paquete")
    a.add_argument("iso_original")
    a.add_argument("iso_nueva")
    a.add_argument("--sin-traduccion", action="store_true", help="solo la Definitive Edition")
    a.add_argument("--perfil", help="perfil de la Definitive Edition: original, comodidad, definitiva o historia")
    a.add_argument("--opcion", action="append", default=[], help="ajuste de la Definitive Edition, por ejemplo deuda=0")
    args = ap.parse_args()
    if args.cmd == "crear":
        create(args.paquete)
    else:
        niveles = niveles_pedidos(args.paquete, args.perfil, args.opcion)
        if args.sin_traduccion and not any(niveles.values()):
            sys.exit("con --sin-traduccion hay que elegir un perfil o alguna opción")
        apply(args.paquete, args.iso_original, args.iso_nueva, not args.sin_traduccion, niveles)


if __name__ == "__main__":
    main()
