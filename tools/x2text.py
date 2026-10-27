"""Texto de Xenosaga Episode II: codificación y formatos que llevan texto.

Codificación (motor de texto de la versión americana: clasificador 0x194DD0 y
glifos 0x1979E0 del ejecutable del disco 1):
  - ASCII: un byte.
  - Pares EUC-JP para los símbolos japoneses. El motor solo reconoce como par:
      fila 0xA4 entera (la localización dibujó ä é ê Ä ® en A4A1-A4A5),
      fila 0xA6 (griego), fila 0xAD (números en círculo),
      A1 + FB BD DA DB DF F9 FA  (○ ― 【 】 × ☆ ★),
      A2 + A2 A3 A4 F6           (□ ■ △ ♪).
  - Cualquier otro byte 0x80-0xFF es un carácter suelto de Windows-1252: la
    fuente trae la tabla completa (glifos 256-383, con ancho proporcional).
    Así se escriben á é í ó ú ñ ¿ ¡ y compañía.
  Consecuencia: ¡ (0xA1) seguido de û ½ Ú Û ß ù ú se leería como par, y los
  bytes sueltos ¤ ¦ y el guion blando (0xA4 0xA6 0xAD) no se pueden usar.
  encode() rechaza esos casos.

Formatos (GsText, más abajo: los textos del GS Path):
  SBL (cf/en/*.sbl, model/map/en/*.sbl): tabla de cadenas de cada escena.
    0x00 "SBL " | u32 versión | u32 cantidad | u32 ? | u32 0 | u32 tabla (0x40)
    | u32 inicio de las cadenas | ceros hasta 0x40 | u32 desplazamientos
    | cadenas terminadas en 0 | relleno a 4 bytes.
    El guion (.sb) las usa por índice, así que pueden cambiar de largo.
  Subtítulos de video (movie/en/*.txt): texto EUC con líneas
    "<tiempo>\\t<texto>"; ';' = comentario; '\\n' literal = salto de línea.
"""
import json
import os
import re
import struct

PAIR_ROWS = {0xA4, 0xA6, 0xAD}
PAIR_CELLS = {0xA1: {0xFB, 0xBD, 0xDA, 0xDB, 0xDF, 0xF9, 0xFA}, 0xA2: {0xA2, 0xA3, 0xA4, 0xF6}}
CUSTOM_A4 = {0xA1: "ä", 0xA2: "é", 0xA3: "ê", 0xA4: "Ä", 0xA5: "®"}
# Caracteres que conviene escribir como el par que ya usa el inglés.
PREFERRED_PAIRS = {"—": b"\xa1\xbd", "―": b"\xa1\xbd"}


def is_pair(lead, trail):
    """Lo que el motor lee como un par (y no como dos bytes sueltos)."""
    return lead in PAIR_ROWS or trail in PAIR_CELLS.get(lead, ())


def decode(data, engine=False):
    """Bytes del juego a texto. Con engine=True se lee como el motor de los
    diálogos (pares solo los reconocidos); si no, todo par EUC válido cuenta
    como par, que es como está escrito el texto original."""
    out, i = [], 0
    while i < len(data):
        b = data[i]
        if b < 0x80:
            out.append(chr(b))
            i += 1
            continue
        trail = data[i + 1] if i + 1 < len(data) else 0
        if is_pair(b, trail) if engine else (b >= 0xA1 and trail >= 0xA1):
            if b == 0xA4 and trail in CUSTOM_A4:
                out.append(CUSTOM_A4[trail])
            else:
                out.append(bytes((b, trail)).decode("euc_jp", errors="replace"))
            i += 2
        else:
            out.append(bytes((b,)).decode("cp1252", errors="replace"))
            i += 1
    return "".join(out)


class EncodeError(ValueError):
    pass


def encode_char(ch):
    if ord(ch) < 0x80:
        return ch.encode("ascii")
    if ch in PREFERRED_PAIRS:
        return PREFERRED_PAIRS[ch]
    try:
        single = ch.encode("cp1252")
        if single[0] not in (0xA4, 0xA6, 0xAD):
            return single
    except UnicodeEncodeError:
        pass
    try:
        pair = ch.encode("euc_jp")
    except UnicodeEncodeError:
        pair = b""
    if len(pair) != 2:
        raise EncodeError(f"carácter que no existe en la fuente: {ch!r}")
    return pair


def encode(text):
    tokens = [encode_char(ch) for ch in text]
    data = b"".join(tokens)
    pos = 0
    for ch, token in zip(text, tokens):
        pos += len(token)
        if len(token) == 1 and token[0] >= 0x80 and pos < len(data) and is_pair(token[0], data[pos]):
            raise EncodeError(f"el juego leería {ch!r} y el carácter siguiente como un símbolo japonés")
    return data


def menu_safe(data, codes=b"\\&$"):
    """Los menús (.txd y textos del ejecutable) pasan el texto por una rutina que lee todo byte
    0x80-0xFF como el primero de un par: una letra con tilde suelta se come el byte siguiente.
    Dentro de una palabra no importa, pero antes de un código (\\n, &NN, $...;) lo rompe ("menú¥nde")
    y al final se come el 0 y mide mal el recuadro (la barra de "Sí" se sale). Un espacio en el
    medio lo evita y no se ve."""
    out, i = bytearray(), 0
    while i < len(data):
        b = data[i]
        if b >= 0x80 and i + 1 < len(data) and is_pair(b, data[i + 1]):
            out += data[i:i + 2]
            i += 2
            continue
        out.append(b)
        i += 1
        if b >= 0x80 and (i == len(data) or data[i] in codes):
            out.append(0x20)
    return bytes(out)


# Ancho en píxeles de cada carácter sin zoom, como lo mide la función 0x195938:
# con las métricas (izquierda, derecha) de font0.us (0x78040, por glifo) es
# derecha - izquierda + 3, y 5 en los glifos vacíos (el espacio). Los glifos
# sin métrica (kanji) miden 19.
WIDTHS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "anchos.json"), encoding="utf-8"))


def width(line):
    """Ancho en píxeles de una línea de texto (los códigos $...; no ocupan lugar)."""
    line = re.sub(r"\$[^;]*;", "", line)
    line = re.sub(r"<[^<>]{1,2}>|&\d\d", "\0", line)  # botones e íconos: un glifo entero
    return sum(WIDTHS.get(ch, 19) for ch in line)


def wrap(text, limit, measure=None):
    """Parte cada párrafo de un texto en líneas de hasta `limit` píxeles, por palabras (medidas
    con la fuente del juego o con `measure`)."""
    measure = measure or width
    out = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            test = f"{line} {word}" if line else word
            if line and measure(test) > limit:
                out.append(line)
                line = word
            else:
                line = test
        out.append(line)
    return "\n".join(out)


class Sbl:
    def __init__(self, data):
        assert data[:4] == b"SBL ", "no es un SBL"
        self.header = bytearray(data[:0x40])
        count, table, start = struct.unpack_from("<I", data, 8)[0], *struct.unpack_from("<2I", data, 0x14)
        offsets = struct.unpack_from(f"<{count}I", data, table)
        self.strings = [data[start + o:data.index(b"\0", start + o)] for o in offsets]

    def to_bytes(self):
        count = len(self.strings)
        table = 0x40
        start = table + 4 * count
        offsets, blob = [], bytearray()
        for s in self.strings:
            offsets.append(len(blob))
            blob += s + b"\0"
        header = bytearray(self.header)
        struct.pack_into("<I", header, 8, count)
        struct.pack_into("<2I", header, 0x14, table, start)
        data = header + struct.pack(f"<{count}I", *offsets) + blob
        return bytes(data + bytes(-len(data) % 4))


class Txd:
    """Tabla de textos de los menús (yosikawa/*.txd): u32 desplazamientos y
    cadenas terminadas en 0, una detrás de otra, sin relleno."""

    def __init__(self, data):
        count = struct.unpack_from("<I", data, 0)[0] // 4
        offsets = struct.unpack_from(f"<{count}I", data, 0)
        self.strings = [data[o:data.index(b"\0", o)] for o in offsets]

    def to_bytes(self):
        offsets, blob, start = [], bytearray(), 4 * len(self.strings)
        for s in self.strings:
            offsets.append(start + len(blob))
            blob += s + b"\0"
        return struct.pack(f"<{len(offsets)}I", *offsets) + bytes(blob)


class Batdat:
    """Base de datos de combate (yamamoto/batdat.us), que también usan los menús.

    u32 cantidad de secciones | u32 tamaño total | u32 inicio de cada sección.
    Las secciones con texto son una tabla de registros de largo fijo con
    punteros u16 (relativos a la sección) a nombre y descripción, seguida de
    las cadenas; la tabla termina justo donde empieza la primera cadena. Las
    secciones empiezan alineadas a 4 bytes.
    """
    # sección: (nombre, largo del registro, campos con puntero: (desplazamiento, nombre del campo))
    LAYOUT = {
        0: ("personajes", 0x5C, ((0, ""),)),
        1: ("enemigos", 0x5C, ((0, ""),)),
        6: ("eteres", 12, ((0, ""), (2, ".desc"))),
        7: ("habilidades", 12, ((0, ""), (2, ".desc"))),
        8: ("accesorios", 16, ((0, ""), (2, ".desc"))),
        9: ("objetos", 16, ((0, ""), (2, ".desc"))),
        10: ("llaves", 4, ((0, ""), (2, ".desc"))),
        11: ("objetos_clave", 8, ((0, ""), (2, ".desc"))),
        12: ("ataques_dobles", 16, ((0, ""), (2, ".desc"))),
        13: ("tecnicas", 16, ((0, ""), (2, ".desc"))),
        14: ("armas_es", 16, ((0, ""), (2, ".desc"))),
        18: ("mensajes", 2, ((0, ""),)),
    }

    def __init__(self, data):
        count = struct.unpack_from("<I", data, 0)[0]
        starts = struct.unpack_from(f"<{count}I", data, 8)
        self.sections = [data[a:b] for a, b in zip(starts, starts[1:] + (len(data),))]
        self.strings = {}  # (sección, posición del puntero) -> cadena
        for sec, (_, size, fields) in self.LAYOUT.items():
            data_sec = self.sections[sec]
            pool, pos = len(data_sec), 0
            while pos < pool:
                for off, _ in fields:
                    target = struct.unpack_from("<H", data_sec, pos + off)[0]
                    pool = min(pool, target)
                    self.strings[(sec, pos + off)] = data_sec[target:data_sec.index(b"\0", target)]
                pos += size

    def keys(self):
        """[(msgctxt, (sección, posición))] en orden: "objetos#3", "objetos#3.desc"..."""
        out = []
        for (sec, pos) in self.strings:
            name, size, fields = self.LAYOUT[sec]
            field = dict(fields)[pos % size]
            out.append((f"{name}#{pos // size}{field}", (sec, pos)))
        return out

    def to_bytes(self):
        sections = list(self.sections)
        for sec in self.LAYOUT:
            table_end = min(struct.unpack_from("<H", self.sections[sec], pos)[0]
                            for (s, pos) in self.strings if s == sec)
            table, pool, placed = bytearray(self.sections[sec][:table_end]), bytearray(), {}
            for (s, pos), text in self.strings.items():
                if s != sec:
                    continue
                if text not in placed:
                    placed[text] = table_end + len(pool)
                    pool += text + b"\0"
                struct.pack_into("<H", table, pos, placed[text])
            sections[sec] = bytes(table + pool + bytes(-len(pool) % 4))
        head = 8 + 4 * len(sections)
        starts, pos = [], head
        for s in sections:
            starts.append(pos)
            pos += len(s)
        return struct.pack(f"<2I{len(sections)}I", len(sections), pos, *starts) + b"".join(sections)


ID = re.compile(rb"[A-Za-z0-9_\-/\\]*[0-9_][A-Za-z0-9_\-/\\]*(\.[a-z]{3})?")  # ce200_905, battle/nag_a_04, movie\cfevent\s-02-02-00-00.ipu...
SPEAKER = re.compile(r"^\[([^\]]+)\]")


def is_text(s):
    """Las cadenas del SBL que se ven en pantalla (las otras son nombres de efectos/voces)."""
    return bool(s) and not ID.fullmatch(s)


SUB_LINE = re.compile(rb"^([+]?[0-9:]+)(\t+)(.*?)(\r?)$")
SUB_FPS = 30  # los tiempos de los subtítulos son minutos:segundos:cuadros


def sub_frames(time):
    m, s, f = map(int, time.split(":"))
    return (m * 60 + s) * SUB_FPS + f


def sub_time(frames):
    return f"{frames // SUB_FPS // 60:02d}:{frames // SUB_FPS % 60:02d}:{frames % SUB_FPS:02d}"


class Subtitles:
    def __init__(self, data):
        self.lines = data.split(b"\n")

    @staticmethod
    def visible(text):
        return bool(text) and not re.fullmatch(rb"(\$[^;]*;)+", text)

    def texts(self):
        """[(número de línea, tiempo, texto en bytes)] de las líneas con texto visible."""
        out = []
        for n, line in enumerate(self.lines):
            m = SUB_LINE.match(line)
            if m and self.visible(m.group(3)):
                out.append((n, m.group(1).decode(), m.group(3)))
        return out

    def replace(self, n, text):
        m = SUB_LINE.match(self.lines[n])
        self.lines[n] = m.group(1) + m.group(2) + text + m.group(4)

    def lengthen(self, cps=15, shortest=SUB_FPS, extra=SUB_FPS, gap=3):
        """Deja más tiempo en pantalla los subtítulos que no alcanzan a leerse, sin adelantar
        ni atrasar su aparición.

        Un subtítulo dura hasta la línea con tiempo que le sigue. Si esa línea es un corte (sin
        texto), se atrasa hasta que el subtítulo dure lo que pide su largo (cps caracteres por
        segundo, y al menos `shortest` cuadros), sin pasar de `extra` cuadros más y dejando
        `gap` cuadros antes de la línea siguiente. El último corte no se mueve: no se sabe dónde
        termina el video."""
        stamps = [(n, m) for n, line in enumerate(self.lines) if (m := SUB_LINE.match(line))]
        for (_, m), (end_n, cut), (_, after) in zip(stamps, stamps[1:], stamps[2:]):
            if not self.visible(m.group(3)) or cut.group(3):
                continue
            start, end = sub_frames(m.group(1).decode()), sub_frames(cut.group(1).decode())
            chars = len(decode(m.group(3)).replace("\\n", " "))
            wanted = start + max(shortest, -(-chars * SUB_FPS // cps))
            new_end = min(wanted, end + extra, sub_frames(after.group(1).decode()) - gap)
            if new_end > end:
                self.lines[end_n] = sub_time(new_end).encode() + cut.group(2) + cut.group(4)

    def to_bytes(self):
        return b"\n".join(self.lines)


def sjis_to_engine(c1, c2):
    """Lo que hace el juego (0x23EBB8) con cada par de bytes de los textos del GS Path: la
    conversión clásica de Shift-JIS a EUC, en 8 bits."""
    v1 = (c1 << 1) & 0xFF
    if c2 < 159:
        o1 = v1 + 31 if (v1 & 0xFE) >= 63 else v1 + 159
        o2 = c2 + 97 if c2 < 127 else c2 + 96
    else:
        o1 = v1 + 32 if (v1 & 0xFE) >= 63 else v1 + 160
        o2 = c2 + 2
    return o1 & 0xFF, o2 & 0xFF


def _gs_pairs():
    """{par que ve el motor: par que hay que escribir}, eligiendo un segundo byte imprimible."""
    def rank(c2):
        return 0 if 0x21 <= c2 <= 0x7E and c2 not in b'"\\' else 1 if c2 >= 0x80 else 2
    out = {}
    for c1 in range(0x80, 0x100):
        for c2 in sorted(range(0x100), key=rank):
            out.setdefault(sjis_to_engine(c1, c2), bytes((c1, c2)))
    return out


GS_PAIRS = _gs_pairs()
NBSP = 0xA0  # espacio duro de 6 píxeles (graficos.py borra el adorno de su glifo); puede ir en un par antes de ¡ ¿ y las tildes


class GsText:
    """Textos del GS Path y de los Segment Files (iwase/Citizen.txt, QuestMes.txt,
    Treasure.txt): bloques "No.N { Clave:"valor" ... }". El juego (0x22EC18) copia cada valor
    a un registro de tamaño fijo: saltea los CR LF, convierte \\n y \\" y trata todo byte
    0x80-0xFF como el primero de un par Shift-JIS, que pasa a EUC (sjis_to_engine). Por eso
    un carácter suelto de Windows-1252 (á é ñ...) tiene que ir dentro de un par junto con la
    letra de al lado, elegido para que la conversión dé justo esos dos bytes."""

    VALUE = re.compile(rb'(\t(\w+):")((?:[^"\\\x80-\xff]|\\.|[\x80-\xff][\x00-\xff])*)"')
    BLOCK = re.compile(rb"No\.(\d+)")

    def __init__(self, data):
        self.data = data
        self.values = []  # [(número, clave, inicio, fin)] del valor entre comillas
        number = None
        pos = 0
        while True:
            b = self.BLOCK.search(data, pos)
            m = self.VALUE.search(data, pos)
            if not m:
                break
            if b and b.start() < m.start():
                number, pos = int(b.group(1)), b.end()
                continue
            self.values.append((number, m.group(2).decode(), m.start(3), m.end(3)))
            pos = m.end()

    @staticmethod
    def to_engine(raw):
        """Bytes del archivo -> lo que queda en el registro del juego."""
        out, i = bytearray(), 0
        while i < len(raw):
            b = raw[i]
            if b == 13 and raw[i + 1:i + 2] == b"\n":
                i += 2
            elif b >= 0x80:
                out += bytes(sjis_to_engine(b, raw[i + 1]))
                i += 2
            elif b == 0x5C:  # \" y \n; con otro carácter se descartan los dos (\( y \) en el inglés)
                out += {0x22: b'"', 0x6E: b"\n"}.get(raw[i + 1], b"")
                i += 2
            else:
                out.append(b)
                i += 1
        return bytes(out)

    @staticmethod
    def from_engine(target):
        """Lo que tiene que quedar en el registro -> bytes del archivo."""
        units, i = [], 0  # [(par que ve el motor, o un byte ASCII)]
        while i < len(target):
            b = target[i]
            nxt = target[i + 1] if i + 1 < len(target) else None
            if b < 0x80:
                units.append(b)
                i += 1
            elif nxt is not None and nxt >= 0x80 and (is_pair(b, nxt) or (b, nxt) in GS_PAIRS):
                units.append((b, nxt))  # símbolo japonés, o dos letras con tilde seguidas (regañó)
                i += 2
            elif units and isinstance(units[-1], int) and (units[-1], b) in GS_PAIRS:
                units.append((units.pop(), b))  # con la letra de antes
                i += 1
            elif nxt is not None and nxt < 0x80 and GS_PAIRS.get((b, nxt), b"\0\0")[1] >= 0x20:
                units.append((b, nxt))  # con la de después
                i += 2
            elif (not units or units[-1] == 0x20) and (NBSP, b) in GS_PAIRS:
                # el espacio de antes pasa a espacio duro (al principio, se agrega uno)
                units[-1:] = [(NBSP, b)]
                i += 1
            elif nxt is not None and nxt < 0x80 and (b, nxt) in GS_PAIRS:
                units.append((b, nxt))  # con la de después, aunque quede un byte de control
                i += 2
            else:
                raise EncodeError(f"{bytes((b,)).decode('cp1252')!r} no puede ir ahí (falta una minúscula al lado)")
        out = bytearray()
        for u in units:
            if isinstance(u, tuple):
                out += GS_PAIRS[u]
            elif u == 0x0A:
                out += b"\\n\r\n"
            elif u == 0x22:
                out += b'\\"'
            else:
                out.append(u)
        return bytes(out)

    def text(self, k):
        _, _, start, end = self.values[k]
        return self.to_engine(self.data[start:end])

    def to_bytes(self, replacements):
        """replacements: {índice del valor: bytes como los ve el motor}."""
        out, pos = bytearray(), 0
        for k, (_, _, start, end) in enumerate(self.values):
            if k in replacements:
                out += self.data[pos:start] + self.from_engine(replacements[k])
                pos = end
        return bytes(out + self.data[pos:])
