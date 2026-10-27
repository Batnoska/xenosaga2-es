"""Exporta los textos del juego a .po e importa la traducción a las ISO.

  traduccion/nombres.po          quién habla ([Shion], [【Second Miltia】]...): se traduce una vez
  traduccion/escenas/<sc>.po     diálogos de cada escena (volumen 0, cf/en/*.sbl)
  traduccion/mapas/<mapa>.po     mensajes de mapas y combate (volumen 0, model/map/en/*.sbl)
  traduccion/videos/<video>.po   subtítulos de los videos (volúmenes 1 y 2, movie/en/*.txt)
  traduccion/menus/<tabla>.po    textos de los menús (volumen 0, yosikawa/*.txd)
  traduccion/datos/batdat.po     nombres y descripciones de objetos, éteres, habilidades,
                                 enemigos... (volumen 0, yamamoto/batdat.us)
  traduccion/gspath/<archivo>.po misiones, ciudadanos y tesoros del GS Path y los Segment
                                 Files (volumen 0, iwase/*.txt): campos de tamaño fijo.
  traduccion/fijos/ejecutable.po textos sueltos del ejecutable (rótulos de estado, tienda...):
                                 se reescriben en su lugar, sin pasarse del espacio que tienen.
                                 Los dos discos traen el mismo ejecutable con otro nombre.
Además se aplican los rótulos dibujados en texturas (tools/graficos.py).

msgctxt: "#<índice>" en los SBL y los .txd, "L<línea>" en los subtítulos y
"<lista>#<n>[.desc]" en batdat.us, "No.<n>/<clave>" en el GS Path y "<posición>/<bytes
disponibles>" en los fijos. Las
traducciones existentes se conservan al volver a exportar. Las entradas
marcadas "fuzzy" son borradores sin revisar.

Uso:
  python tools/textos.py exportar
  python tools/textos.py importar [--solo-revisados] [--disco 1|2]
"""
import argparse
import collections
import glob
import os
import re

import graficos
import po
from x2iso import Iso, Volume, build, iso_paths
from x2text import SPEAKER, Batdat, EncodeError, GsText, Sbl, Subtitles, Txd, decode, encode, is_text, menu_safe, width

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "traduccion")
NAMES = os.path.join(OUT, "nombres.po")
SOURCES = {  # carpeta de .po: (volumen, patrón, tipo)
    "escenas": (0, "cf/en/*.sbl", "sbl"),
    "mapas": (0, "model/map/en/*.sbl", "sbl"),
    "videos": (None, "movie/en/*.txt", "sub"),
    "menus": (0, "yosikawa/*.txd", "txd"),
    "datos": (0, "yamamoto/batdat.us", "bat"),
    "gspath": (0, "iwase/*[a-z].txt", "gs"),  # Citizen, QuestMes, Treasure (los *2.txt son los japoneses, sin usar)
}
# Zonas del ejecutable (SLUS_208.92 = SLUS_211.33) con textos de la interfaz (el resto son textos de
# depuración, rutas y nombres de funciones). Cada texto se reemplaza en su lugar.
FIXED = {
    "ejecutable": [(0x19E0F0, 0x19E108), (0x1988B0, 0x1989B0), (0x2CD9A8, 0x2CDA40), (0x56BA00, 0x56BB60),
                    (0x56BF80, 0x56C820), (0x56E3C0, 0x56E4D0), (0x57E530, 0x57E560), (0x57E600, 0x57EA80)],
}
NOT_UI = re.compile(r"[\\#]|\w/\w|%[-0-9.]*[dsxpfuc]|^\$|\.(c|bin|xtx)$|^[a-z]+[A-Z0-9]\w*$|^[a-z_]+$|^\d|^img|_menu$")
# Ancho (píxeles) del nombre más largo de cada lista de batdat.us: hasta ahí entra en los menús.
# Textos del GS Path y los Segment Files: {archivo: {clave: (bytes, píxeles, líneas)}}. Los bytes
# son el tamaño del campo en el registro del juego (0x22EE94, 0x22F0A4, 0x2321FC) menos el 0 final;
# los píxeles y las líneas, lo más ancho y lo más largo del inglés (el tamaño del recuadro).
GS_FIELDS = {
    "Citizen": {"Name": (16, 137, 1), "Sex": (6, 59, 1), "Age": (16, 106, 1), "Hobby": (22, 194, 1),
                "Profile": (150, 422, 3)},
    "QuestMes": {"Subject": (30, 269, 1), "Locate": (16, 151, 1), "Client": (16, 125, 1), "MesIPG": (256, 275, 5),
                 "MesSCD": (256, 275, 5), "MesFLD": (256, 275, 5), "UkunSCD": (1024, 220, 16),
                 "UkunFLD": (1024, 220, 16)},
    "Treasure": {"Item": (20, 153, 1), "Locate": (26, 171, 1), "Expl": (120, 216, 5)},
}
NAME_WIDTH = {"personajes": 96, "enemigos": 166, "eteres": 149, "habilidades": 144, "accesorios": 174,
              "objetos": 141, "llaves": 121, "objetos_clave": 187, "ataques_dobles": 180, "tecnicas": 138,
              "armas_es": 145, "mensajes": 206}
HEADER = {
    "Project-Id-Version": "Xenosaga Episode II - traducción al español",
    "Language": "es_419",
    "MIME-Version": "1.0",
    "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit",
}
CODES = re.compile(r"\$[^;]*;|<[^<>]{1,2}>|&\d\d|●")  # formato, botones (<○>, &01...) y fin de página
NOTE_CODES = "No modificar los códigos $...;, los botones <...> y &NN, ni el ● de fin de página."
NOTE_SUB = "Subtítulo: un tramo de la frase, sincronizado con la voz. Máximo 2 líneas."
NOTE_CUTSCENE = "Cinemática: subtítulo sobre la imagen, sin recuadro. Cada línea tiene que entrar en pantalla."
CUTSCENE_WIDTH = 460  # píxeles: la línea más ancha de las cinemáticas originales ronda los 450


def to_po(text):
    return text.replace("\\n", "\n")


def from_po(text):
    return text.replace("\n", "\\n")


def split_speaker(text):
    m = SPEAKER.match(text)
    return (m.group(1), text[m.end():]) if m else (None, text)


def is_debug(text):
    """Mensajes de prueba de los programadores: en Shift-JIS (no decodifican) o solo en japonés."""
    return "�" in text or (re.search("[぀-ヿ]", text) and not re.search("[A-Za-z]{3}", text))


def sbl_entries(data):
    """[(msgctxt, nombre o None, texto)] de un SBL."""
    out = []
    for i, s in enumerate(Sbl(data).strings):
        if is_text(s) and not is_debug(decode(s)):
            name, text = split_speaker(decode(s))
            out.append((f"#{i}", name, to_po(text)))
    return out


def is_menu_text(text):
    """Textos de un .txd que se ven: no los comandos del tutorial (%p, %t45, *...)
    ni los huecos de reserva."""
    return bool(text) and not is_debug(text) and not re.fullmatch(
        r"%\w[\w+-]*|\*|//.*|(?i:-reserve-|.+ reserve)", text)


def txd_entries(data):
    """[(msgctxt, texto)] de un .txd."""
    return [(f"#{i}", to_po(decode(s))) for i, s in enumerate(Txd(data).strings) if is_menu_text(decode(s))]


def bat_entries(data):
    """[(msgctxt, texto)] de batdat.us, sin los huecos de reserva (予備, 敵19...)."""
    bat = Batdat(data)
    return [(ctx, to_po(decode(bat.strings[key]))) for ctx, key in bat.keys()
            if re.search("[A-Za-z]", decode(bat.strings[key]))]


# Un texto suelto termina en 0 o sigue con un código de control (0x19 = color, en el formato
# de los mensajes del sistema: "\x0b\r\x03\x19\x03Pause\x19\x00").
FIXED_TEXT = re.compile(rb"(?<=[\x00-\x1f])[\x20-\x7e\xa1-\xfe][\x20-\x7e\x80-\xfe]*(?=[\x00\x19])")


def fixed_entries(data, ranges):
    """[(msgctxt "<posición>/<bytes>", texto)] de las cadenas de la interfaz dentro de las zonas.
    Si después vienen ceros, el texto puede ocuparlos; si viene un código, no puede crecer."""
    out = []
    for lo, hi in ranges:
        for m in FIXED_TEXT.finditer(data[lo - 1:hi]):
            text, start = decode(m.group()), lo - 1 + m.start()
            room = end = start + len(m.group())
            while data[end] == 0 and room < len(data) and data[room] == 0:
                room += 1
            room = room - start - (1 if data[end] == 0 else 0)
            if re.search("[A-Za-z]{2}", text) and not NOT_UI.search(text.replace("\\n", " ")):
                out.append((f"{start:#x}/{room}", to_po(text)))
    return out


def patch_fixed(data, table):
    """Reescribe en su lugar los textos sueltos traducidos: rellena con ceros si el original
    terminaba en 0, o con espacios si seguía un código de control."""
    data = bytearray(data)
    for ctx, text in table.items():
        pos, room = (int(x, 0) for x in ctx.split("/"))
        new = menu_safe(encode(from_po(text)))
        end = pos
        while data[end] not in (0, 0x19):
            end += 1
        if data[end] == 0:
            data[pos:pos + room + 1] = new + bytes(room + 1 - len(new))
        else:
            data[pos:end] = new + b" " * (end - pos - len(new))
    return bytes(data)


# Mensajes del ejecutable con códigos de control en bytes crudos (color 0x0C xx, tamaño 0x19 xx, los
# íconos ○ y × como pares EUC, la ® como el par A4 A5): no pasan bien por un .po, así que se
# traducen acá, tramo por tramo, y los códigos quedan. {posición: [(inglés, español)]}
EXE_MESSAGES = {
    0x19E030: [("Please insert DISC 2 of", "Inserta el DISCO 2 de")],  # cambio de disco
    0x19E060: [("Incorrect disc.", "Disco incorrecto."), ("Please insert DISC 2 of", "Inserta el DISCO 2 de")],
    0x19E0A0: [("There is no disc inserted.", "No hay ningún disco."), ("Please insert DISC 2 of", "Inserta el DISCO 2 de")],
    0x56949F: [("Save Xenosaga Episode II clear data?", "¿Guardar datos de partida completada?"),
               (" button: Yes", ": Sí "), (" button: No", ": No")],
    0x5694FF: [("Ending without saving.", "Terminar sin guardar."), ("Is this okay?", "¿Confirmas?"),
               (" button: Yes", ": Sí "), (" button: No", ": No")],
    0x569597: [("Save game data?", "¿Guardar los datos?"), (" button: Yes", ": Sí "), (" button: No", ": No")],
    0x5695E7: [("Continuing without saving.", "Continuar sin guardar."), ("Is this okay?", "¿Confirmas?"),
               (" button: Yes", ": Sí "), (" button: No", ": No")],
    # tarjeta de memoria al empezar
    0x583180: [("requires 34KB of free space to\nsave data.", "necesita 34KB libres\npara guardar datos.")],
    0x5831C8: [("No memory card (8MB) (for PlayStation", "No hay tarjeta de memoria (8MB) (para PlayStation"),
               ("in MEMORY CARD slot 1 and MEMORY CARD slot 2.", "en las ranuras de MEMORY CARD 1 y 2.")],
    0x583228: [("Insufficient space on\nmemory card (8MB) (for PlayStation", "Falta espacio en la\ntarjeta de memoria (8MB) (para PlayStation"),
               ("in MEMORY CARD slot 1.", "de la ranura 1.")],
    0x583280: [("Insufficient space on\nmemory card (8MB) (for PlayStation", "Falta espacio en la\ntarjeta de memoria (8MB) (para PlayStation"),
               ("in MEMORY CARD slot 2.", "de la ranura 2.")],
    0x5832D8: [("Insufficient space on\nmemory card (8MB) (for PlayStation", "Falta espacio en las\ntarjetas de memoria (8MB) (para PlayStation"),
               ("in MEMORY CARD slot 1 and MEMORY CARD slot 2.", "de las ranuras 1 y 2.")],
    0x583348: [("Start game?", "¿Empezar la partida?"), (" button: Yes/", ": Sí /"), (" button: No", ": No")],
    0x583390: [("Please insert a memory card (8MB) (for PlayStation", "Inserta una tarjeta de memoria (8MB) (para PlayStation"),
               ("with at least 34KB of free space into\nMEMORY CARD slot 1 or MEMORY CARD slot 2.",
                "con al menos 34KB libres en la ranura\nde MEMORY CARD 1 o 2."),
               (" button: Cancel", ": Cancelar")],
}


def _message_end(data, pos):
    """Fin de un mensaje: el primer 0 que no es parámetro de un código 0x19."""
    while data[pos]:
        pos += 2 if data[pos] == 0x19 else 1
    return pos


def patch_messages(data, exe=None):
    """Aplica EXE_MESSAGES; el nuevo puede ocupar también los ceros que siguen al original. Con
    `exe` (el ejecutable original), los mensajes se buscan por su contenido en otro archivo
    (OV02.OVL trae una copia de los de la tarjeta de memoria) y se aplican los que estén."""
    data = bytearray(data)
    for pos, pairs in EXE_MESSAGES.items():
        if exe is not None:
            pos = bytes(data).find(exe[pos:_message_end(exe, pos) + 1])
            if pos < 0:
                continue
        end = _message_end(data, pos)
        room = end
        while data[room] == 0:
            room += 1
        new = bytes(data[pos:end])
        for old, text in pairs:
            assert old.encode() in new, f"{pos:#x}: no está {old!r}"
            enc = encode(text)
            # una letra con tilde no puede quedar antes de un salto o un código (ver menu_safe)
            assert not any(b >= 0x80 and enc[k + 1:k + 2] in (b"", b"\n") for k, b in enumerate(enc)), f"{text!r}"
            new = new.replace(old.encode(), enc)
        assert len(new) < room - pos, f"{pos:#x}: {len(new)} bytes, entran {room - pos - 1}"
        data[pos:room] = new + bytes(room - pos - len(new))
    return bytes(data)


def gs_field(path, ctx):
    """(bytes, píxeles, líneas) del campo de un texto del GS Path: iwase/Citizen.txt + "No.1/Name"."""
    return GS_FIELDS[os.path.basename(path).rsplit(".", 1)[0]][ctx.split("/")[1]]


def gs_entries(data):
    """[(msgctxt "No.<n>/<clave>", texto)] de un texto del GS Path o de los Segment Files."""
    gs = GsText(data)
    texts = [decode(gs.text(k), engine=True) for k in range(len(gs.values))]
    return [(f"No.{n}/{key}", text) for (n, key, _, _), text in zip(gs.values, texts) if re.search("[A-Za-z]", text)]


def sub_entries(data):
    """[(msgctxt, tiempo, texto)] de un archivo de subtítulos."""
    return [(f"L{n}", time, to_po(decode(text))) for n, time, text in Subtitles(data).texts()
            if "�" not in decode(text)]


def keep_old(path, entries):
    if os.path.exists(path):
        _, old = po.read(path)
        done = {o.msgctxt: o for o in old if o.msgstr}
        for e in entries:
            o = done.get(e.msgctxt)
            if o and o.msgid == e.msgid:
                e.msgstr, e.fuzzy = o.msgstr, o.fuzzy


def export():
    isos = [Iso(p) for p in iso_paths()]
    names, total, files = collections.Counter(), 0, 0
    for folder, (group, pattern, kind) in SOURCES.items():
        os.makedirs(os.path.join(OUT, folder), exist_ok=True)
        sources = []
        if group is None:  # subtítulos: el volumen propio de cada disco
            for iso in isos:
                vol = Volume(iso, iso.groups[-1])
                sources += [(vol, e) for e in vol.find(pattern)]
        else:
            vol = Volume(isos[0], group)
            sources = [(vol, e) for e in vol.find(pattern)]
        for vol, e in sources:
            data = vol.read(e)
            entries = []
            cutscene = kind == "sbl" and b"motion/cfevent/" in data  # guion de una cinemática
            if kind == "sbl":
                for ctx, name, text in sbl_entries(data):
                    notes = [NOTE_CUTSCENE] if cutscene else []
                    if name:
                        names[name] += 1
                        notes.append(f"habla: {name}")
                    if CODES.search(text):
                        notes.append(NOTE_CODES)
                    if "\n" in text and all(len(line) <= 32 for line in text.split("\n")):
                        notes.append(f"Opciones: una por línea. Mantener {text.count(chr(10)) + 1} líneas en el mismo orden.")
                    entries.append(po.Entry(ctx, text, comments=notes))
            elif kind in ("txd", "bat"):
                for ctx, text in (txd_entries if kind == "txd" else bat_entries)(data):
                    entries.append(po.Entry(ctx, text, comments=[NOTE_CODES] if CODES.search(text) else []))
            elif kind == "gs":
                fields = GS_FIELDS[os.path.basename(e.path).rsplit(".", 1)[0]]
                for ctx, text in gs_entries(data):
                    size, px, lines = fields[ctx.split("/")[1]]
                    note = f"máximo {size} caracteres; {lines} línea(s) de hasta {px} píxeles"
                    entries.append(po.Entry(ctx, text, comments=[note]))
            else:
                subs = sub_entries(data)
                for k, (ctx, time, text) in enumerate(subs):
                    notes = [f"tiempo {time}", NOTE_SUB]
                    prev = subs[k - 1][2] if k else ""
                    if prev and not re.search(r"[.!?…―]\W*$", prev):
                        notes.append("viene de: " + prev.replace("\n", " "))
                    entries.append(po.Entry(ctx, text, comments=notes))
            name = os.path.basename(e.path).rsplit(".", 1)[0]
            path = os.path.join(OUT, folder, name + ".po")
            if not entries:
                if os.path.exists(path):  # ya no tiene textos (cambió el filtro)
                    os.remove(path)
                continue
            keep_old(path, entries)
            header = {**HEADER, "X-Xeno-Source": f"{vol.group}:{e.path}"}
            if cutscene:
                header["X-Xeno-Tipo"] = "cinematica"
            po.write(path, header, entries)
            total += len(entries)
            files += 1
    os.makedirs(os.path.join(OUT, "fijos"), exist_ok=True)
    for name, ranges in FIXED.items():
        entries = [po.Entry(ctx, text, comments=[f"máximo {ctx.split('/')[1]} bytes"])
                   for ctx, text in fixed_entries(isos[0].read_file(isos[0].executable), ranges)]
        path = os.path.join(OUT, "fijos", name + ".po")
        keep_old(path, entries)
        po.write(path, {**HEADER, "X-Xeno-Source": f"raiz:{name}"}, entries)
        total += len(entries)
        files += 1
    entries = [po.Entry(n, n, comments=[f"aparece {c} veces"]) for n, c in sorted(names.items())]
    keep_old(NAMES, entries)
    po.write(NAMES, {**HEADER, "X-Xeno-Source": "nombres"}, entries)
    print(f"{total} textos en {files} archivos y {len(entries)} nombres")


def check(src, dst, kind, cutscene=False, ctx="", field=None):
    """(errores, avisos) de una traducción; field: (bytes, píxeles, líneas) en los textos del GS Path."""
    errors, warnings = [], []
    if kind == "gs":
        size, px, lines = field
        try:
            used = len(GsText.to_engine(GsText.from_engine(encode(dst))))
            if used > size:
                errors.append(f"no entra: ocupa {used} bytes y el campo tiene {size}")
        except EncodeError as exc:
            errors.append(str(exc))
        if max(width(line) for line in dst.split("\n")) > px + 4:
            warnings.append(f"línea más ancha que el recuadro ({px} píxeles)")
        if dst.count("\n") + 1 > lines:
            warnings.append(f"más de {lines} línea(s)")
        return errors, warnings
    if sorted(CODES.findall(src)) != sorted(CODES.findall(dst)):
        errors.append("los códigos $...; o <...> no coinciden con el original")
    if src.count("%") != dst.count("%"):
        errors.append("el juego escribe el signo de porcentaje como %%: mantener los mismos que el original")
    try:
        encoded = menu_safe(encode(from_po(dst)))
        if kind == "fijo" and len(encoded) > int(ctx.split("/")[1]):
            errors.append(f"no entra: ocupa {len(encoded)} bytes y hay {ctx.split('/')[1]}")
    except EncodeError as exc:
        errors.append(str(exc))
    if kind in ("sbl", "txd", "bat") and "\n" in src:
        # Con renglones cortos son recuadros de ancho fijo (combate, tutoriales, carteles,
        # opciones), que recortan lo que no entra; los diálogos largos los acomoda el juego.
        widest = max(width(line) for line in src.split("\n"))
        # Las descripciones de batdat.us comparten una ventana de ayuda ancha (hasta ~700 px en inglés).
        if widest <= 560 and max(width(line) for line in dst.split("\n")) > max(widest + 4, 600 if kind == "bat" else 400):
            warnings.append("línea más ancha que el original: puede cortarse en el recuadro")
    if cutscene and max(width(line) for line in dst.split("\n")) > max(
            CUTSCENE_WIDTH, *(width(line) for line in src.split("\n"))):
        warnings.append("línea muy ancha: puede salirse de la pantalla")
    if kind == "bat" and not ctx.endswith(".desc") and width(dst) > max(width(src), NAME_WIDTH[ctx.split("#")[0]]):
        warnings.append("nombre más ancho que el más largo de su lista: puede no entrar en el menú")
    if kind == "txd" and "\n" not in src and width(src) <= 130 and width(dst) > width(src) + max(20, width(src) // 4):
        # Opciones y títulos de menú: van en columnas de ancho fijo.
        warnings.append("opción de menú bastante más larga que el original: puede no entrar")
    if kind == "sbl" and src.count("\n") != dst.count("\n"):
        # Varias líneas cortas son opciones (Sí/No...): el guion espera la misma cantidad.
        if not cutscene and "\n" in src and all(len(line) <= 32 for line in src.split("\n")):
            errors.append("las opciones tienen que tener la misma cantidad de líneas")
        else:
            warnings.append("cambió la cantidad de líneas")
    if kind == "sub":
        widest = max(len(line) for line in src.split("\n"))
        lines = dst.split("\n")
        if len(lines) > 2:
            warnings.append("subtítulo de más de 2 líneas")
        if max(len(line) for line in lines) > max(52, widest + 4):
            warnings.append("línea de subtítulo larga")
    return errors, warnings


def load(reviewed_only):
    """Traducciones por archivo: {(volumen, ruta): {msgctxt: texto}}, nombres y problemas."""
    problems, result = [], {}
    names = {}
    if os.path.exists(NAMES):
        for e in po.read(NAMES)[1]:
            if e.msgstr and not (reviewed_only and e.fuzzy):
                names[e.msgctxt] = e.msgstr
    for folder, (_, _, kind) in list(SOURCES.items()) + [("fijos", (None, None, "fijo"))]:
        for path in sorted(glob.glob(os.path.join(OUT, folder, "*.po"))):
            header, entries = po.read(path)
            group, src = header["X-Xeno-Source"].split(":", 1)
            cutscene = header.get("X-Xeno-Tipo") == "cinematica"
            table = {}
            for e in entries:
                if not e.msgstr or (reviewed_only and e.fuzzy):
                    continue
                field = gs_field(src, e.msgctxt) if kind == "gs" else None
                errors, warnings = check(e.msgid, e.msgstr, kind, cutscene, e.msgctxt, field)
                where = f"{os.path.relpath(path, ROOT)} [{e.msgctxt}]"
                problems += [f"ERROR {where}: {m}" for m in errors] + [f"aviso {where}: {m}" for m in warnings]
                if not errors:
                    table[e.msgctxt] = e.msgstr
            result[(group if group == "raiz" else int(group), src)] = (kind, table)
    return result, names, problems


def apply(kind, data, table, names):
    """Bytes del archivo traducido, o None si no cambia."""
    if kind == "sbl":
        sbl = Sbl(data)
        changed = False
        for i, s in enumerate(sbl.strings):
            if not is_text(s) or is_debug(decode(s)):
                continue
            name, text = split_speaker(decode(s))
            new_name = names.get(name, name) if name else None
            new_text = table.get(f"#{i}")
            if new_text is None and new_name == name:
                continue
            text = from_po(new_text) if new_text is not None else text
            # las opciones (Sí\nNo...) las arma la rutina de los menús; en los diálogos solo
            # importa el final de la cadena
            options = "\\n" in text and all(len(line) <= 32 for line in text.split("\\n"))
            sbl.strings[i] = menu_safe(encode((f"[{new_name}]" if name else "") + text), b"\\&$" if options else b"")
            changed = True
        return sbl.to_bytes() if changed else None
    if kind == "bat":
        bat = Batdat(data)
        keys = dict(bat.keys())
        for ctx, text in table.items():
            bat.strings[keys[ctx]] = menu_safe(encode(from_po(text)))
        return bat.to_bytes() if table else None
    if kind == "txd":
        txd = Txd(data)
        for key, text in table.items():
            txd.strings[int(key[1:])] = menu_safe(encode(from_po(text)))
        return txd.to_bytes() if table else None
    if kind == "gs":
        gs = GsText(data)
        index = {f"No.{n}/{key}": k for k, (n, key, _, _) in enumerate(gs.values)}
        return gs.to_bytes({index[ctx]: encode(text) for ctx, text in table.items()}) if table else None
    subs = Subtitles(data)
    for n, _, _ in subs.texts():
        if f"L{n}" in table:
            subs.replace(n, encode(from_po(table[f"L{n}"])))
    subs.lengthen()
    return subs.to_bytes() if table else None


def import_(reviewed_only, discs):
    translations, names, problems = load(reviewed_only)
    first = Iso(iso_paths()[0])
    reference_exe = first.read_file(first.executable)  # los desplazamientos de los fijos son de este
    for p in problems:
        print(p)
    for disc in discs:
        iso_path = iso_paths()[disc - 1]
        iso = Iso(iso_path)
        replacements = {}
        for group in iso.groups:
            vol = Volume(iso, group)
            for (g, src), (kind, table) in translations.items():
                if g != group or kind == "fijo" or src not in vol.by_path:
                    continue
                if not table and not (kind == "sbl" and names):
                    continue
                new = apply(kind, vol.read(vol.by_path[src]), table, names)
                if new is not None:
                    replacements[(group, src)] = new
            if group == 0:  # rótulos dibujados en las texturas
                replacements.update(graficos.replacements(lambda g, path: vol.read(vol.by_path[path])))
        loose = {}
        for (g, name), (kind, table) in translations.items():
            if g == "raiz" and name == "ejecutable" and table:
                exe = iso.read_file(iso.executable)
                if exe != reference_exe:
                    print(f"ERROR {iso.executable}: no es el ejecutable conocido; textos sueltos sin aplicar")
                    continue
                loose[iso.executable] = graficos.patch_exe(patch_messages(patch_fixed(exe, table)))
                loose["OV02.OVL"] = patch_messages(iso.read_file("OV02.OVL"), exe)
        loose["OV01.OVL"] = graficos.patch_ov01(iso.read_file("OV01.OVL"))  # recortes de los carteles del combate
        out = os.path.join(ROOT, "work", f"xenosaga2_es_disco{disc}.iso")
        build(iso_path, out, replacements, loose)
    errors = sum(p.startswith("ERROR") for p in problems)
    print(f"{errors} textos con errores (no aplicados)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("exportar")
    p = sub.add_parser("importar")
    p.add_argument("--solo-revisados", action="store_true", help="ignorar los borradores (fuzzy)")
    p.add_argument("--disco", type=int, choices=(1, 2), action="append", help="por defecto, los dos")
    args = ap.parse_args()
    if args.cmd == "exportar":
        export()
    else:
        import_(args.solo_revisados, args.disco or [1, 2])


if __name__ == "__main__":
    main()
