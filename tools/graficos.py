"""Rótulos en inglés dibujados en las texturas de la interfaz (comandos de combate, ficha...).

Las letras nuevas salen de la misma textura: se recortan de las palabras originales y se
vuelven a combinar, así el texto conserva la tipografía, el tamaño y el sombreado del juego.
Cada letra se recorta con las filas de su palabra (así conserva la altura respecto de la
celda). En las fuentes con borde suavizado (comandos de combate), una letra son columnas de
trazo pleno (índice >= INK) más una columna de borde a cada lado, que se comparte con la
letra vecina; en las demás, las letras están separadas por columnas vacías.

El juego dibuja cada rótulo recortando un rectángulo fijo de la textura (la "celda"), así
que el texto nuevo tiene que entrar en la celda del original:
  - comandos de combate (82 x 17): OV01.OVL, tabla (id, u, v) en 0x37588; el tamaño está en
    el código que la usa (0xAA5684).
  - ficha de estado y otros de yosikawa/font.xtx: ejecutable, tabla de 16 bytes por recorte
    (u, v, ancho, alto, 0, textura, 0, 0) en 0x2C8EE2.

Uso:
  python tools/graficos.py ver     vistas previas en work/tex/es_*.png (original arriba)
"""
import io
import os
import struct
import sys
import zlib

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from x2tex import Txy, Xtx
from x2text import wrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK = 128  # en la fuente de los comandos el trazo pleno ronda el índice 144; debajo son bordes
FAINT = 5  # en las fuentes de 16 niveles, debajo de esto es el borde suavizado
ACCENTED = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}


class Sheet:
    """Una textura .xtx: la memoria de video donde se carga, vista con índices de 8 o 4 bits."""

    def __init__(self, data):
        self.xtx = Xtx(data)
        self.gs = self.xtx.memory()

    def view(self, psm):
        w, h, px = self.xtx.read(self.gs, psm)
        return Image.frombytes("L", (w, h), px)

    def put(self, psm, img):
        self.xtx.write(self.gs, psm, img.tobytes())

    def to_bytes(self):
        return self.xtx.store(self.gs)


class Glyph:
    """Letra recortada: imagen, fila donde empieza (respecto de la celda) y columnas de borde
    que comparte con cada vecina (0 o 1)."""

    def __init__(self, img, dy, edge):
        self.img, self.dy, self.edge = img, dy, edge

    @property
    def advance(self):
        return self.img.width - self.edge

    def narrow(self):
        """La misma letra una columna más angosta (se quita la columna central)."""
        w, h = self.img.size
        mid = w // 2
        out = Image.new("L", (w - 1, h))
        out.paste(self.img.crop((0, 0, mid, h)), (0, 0))
        out.paste(self.img.crop((mid + 1, 0, w, h)), (mid, 0))
        return Glyph(out, self.dy, self.edge)


def cut_word(img, cell, word, edge=1):
    """Letras de una palabra dentro de su celda (u, v, ancho, alto): {letra: Glyph}."""
    u, v, w, h = cell
    px = img.load()
    rows = [y for y in range(v, v + h) if any(px[x, y] for x in range(u, u + w))]
    top, bottom = rows[0], rows[-1] + 1
    if edge:  # columna de trazo: dos píxeles plenos o más (en ESCAPE, la A toca a la C en uno)
        cols = [sum(px[x, y] >= INK for y in range(top, bottom)) >= 2 for x in range(u, u + w)]
    else:  # sin contar los píxeles tenues, que a veces unen dos letras (la P y la t de C.Pt)
        cols = [max(px[x, y] for y in range(top, bottom)) >= FAINT for x in range(u, u + w)]
    runs, start = [], None
    for i, c in enumerate(cols + [False]):
        if c and start is None:
            start = i
        elif not c and start is not None:
            runs.append((u + start, u + i))
            start = None
    letters = word.replace(" ", "")
    assert len(runs) == len(letters), f"{word}: {len(runs)} letras en la textura"
    out = {}
    for (a, b), ch in zip(runs, letters):
        if not edge:  # y después la columna tenue de cada lado, si la hay
            a -= any(px[a - 1, y] for y in range(top, bottom))
            b += any(px[b, y] for y in range(top, bottom))
        g = img.crop((a - edge, top, b + edge, bottom))
        if edge:  # en los bordes solo queda lo que toca a esta letra (no el borde de la vecina)
            gp = g.load()
            for y in range(g.height):
                if not gp[1, y]:
                    gp[0, y] = 0
                if not gp[g.width - 2, y]:
                    gp[g.width - 1, y] = 0
        out.setdefault(ch, Glyph(g, top - v, edge))
    return out


def letter_j(u):
    """J a partir de la U: sin la mitad de arriba del palo izquierdo."""
    img = u.img.copy()
    px = img.load()
    for y in range(img.height // 2):
        for x in range(5):
            px[x, y] = 0
    y = img.height // 2  # punta del gancho, suavizada como el arranque de los palos
    px[1, y] = min(px[1, y], 110)
    return Glyph(img, u.dy, u.edge)


def accent(img, x, y, full=144, edge=100):
    """Tilde de tres filas desde (x, y): diagonal de dos píxeles de grueso, con borde suavizado."""
    px = img.load()
    for row in range(3):
        left = x + 2 - row
        for dx, val in ((0, edge), (1, full), (2, full), (3, edge)):
            px[left + dx, y + row] = max(px[left + dx, y + row], val)


def draw(img, cell, text, font, left=0, gap=0, space=4):
    """Borra la celda y escribe el texto alineado a la izquierda, como los originales: la
    primera letra en la columna `left` de la celda, `gap` columnas vacías entre letras."""
    u, v, w, h = cell
    img.paste(0, (u, v, u + w, v + h))
    glyphs = [None if ch == " " else font[ACCENTED.get(ch, ch)] for ch in text]

    def end():
        x = left
        for g in glyphs:
            x += space if g is None else g.advance + gap
        return x - gap + max(g.edge for g in glyphs if g)

    # si no entra, se angostan las letras más anchas de a una columna
    while end() > w:
        i = max((k for k, g in enumerate(glyphs) if g), key=lambda k: glyphs[k].advance)
        assert glyphs[i].advance > 9, f"{text!r} no entra en {w} píxeles"
        glyphs[i] = glyphs[i].narrow()
    shift = 1 if any(ch in ACCENTED for ch in text) else 0  # lugar para la tilde
    x = u + left
    for ch, g in zip(text, glyphs):
        if g is None:
            x += space
            continue
        top = v + g.dy + shift
        assert top + g.img.height <= v + h and (not shift or top - 3 >= v), f"{text!r} no entra en {h} filas"
        region = img.crop((x, top, x + g.img.width, top + g.img.height))
        img.paste(ImageChops.lighter(region, g.img), (x, top))  # el borde compartido: el más claro
        if ch in ACCENTED:
            accent(img, x + g.advance // 2, top - 3)  # la fila top es el borde suave
        x += g.advance + gap


# Comandos del menú de combate (yamamoto/stat/stat.xtx, índices de 8 bits).
STAT = "yamamoto/stat/stat.xtx"
COMMAND_CELLS = {  # texto original: celda (u, v, ancho, alto)
    "STOCK": (256, 130, 82, 17), "ETHER": (256, 147, 82, 17), "ITEM": (256, 164, 82, 17),
    "DOUBLE": (256, 181, 82, 17), "CHANGE": (338, 130, 82, 17), "SPECIAL": (338, 147, 82, 17),
    "ESCAPE": (338, 164, 82, 17), "MOVE": (338, 181, 82, 17),
}
# De dónde sale cada letra: la primera palabra de esta lista que la tenga.
COMMAND_SOURCES = ["DOUBLE", "ETHER", "CHANGE", "ESCAPE", "SPECIAL", "STOCK", "ITEM", "MOVE"]
COMMANDS = {
    "ETHER": "ÉTER", "ITEM": "OBJETO", "DOUBLE": "DOBLE", "CHANGE": "CAMBIO",
    "SPECIAL": "TÉCNICA", "ESCAPE": "HUIR", "MOVE": "MOVER",
}  # STOCK queda igual (glosario)


def stat(sheet, read):
    img = sheet.view(8)
    font = {}
    for word in COMMAND_SOURCES:
        for ch, g in cut_word(img, COMMAND_CELLS[word], word).items():
            font.setdefault(ch, g)
    font["J"] = letter_j(font["U"])
    for word, text in COMMANDS.items():
        draw(img, COMMAND_CELLS[word], text, font)
    sheet.put(8, img)
    popups(sheet)


# Carteles en cursiva del combate (misma textura): letra tipo Arial Black inclinada, rellena con un
# degradé que va por fila (de 0xFA arriba a 0x88 abajo) y con un borde oscuro de 2 píxeles (0x09).
# Se escriben de nuevo con Arial Black inclinada, con el degradé de cada fila y el borde de los
# originales. Recortes en OV01.OVL: tabla (u, v, ancho, alto) de enteros de 32 bits en 0x37608
# (índice en la tabla) y, "Zone" e "Intercept", inmediatos en el código (fijos acá). Las filas se
# reparten de nuevo: cada palabra va en [u, u + ancho) y se angosta si no entra.
POPUP_FONT = "C:/Windows/Fonts/ariblk.ttf"
POPUP_SLANT = 0.21  # columnas por fila
POPUPS = [  # (índice en la tabla o None, recorte original (u, v, ancho, alto), u y ancho nuevos, texto, alto de la mayúscula)
    (13, (256, 0, 128, 18), (256, 128), "Sin Desequilibrio", 13),
    (14, (256, 18, 128, 18), (256, 128), "Sin Elevación", 13),
    (15, (256, 36, 128, 18), (256, 128), "Sin Derribo", 13),
    (12, (383, 0, 93, 18), (383, 93), "Ptos. hab.", 13),  # sigue "x" y el número
    (None, (384, 36, 56, 18), (384, 56), "Zona", 13),  # siguen A, B o C
    (None, (384, 54, 128, 20), (384, 128), "Intercepción", 13),
    (10, (256, 86, 112, 18), (256, 120), "Turno anulado", 13),
    (0, (370, 86, 57, 18), (377, 40), "Haz", 13),
    (11, (429, 86, 80, 18), (418, 91), "Por detrás", 13),
    (2, (256, 107, 70, 18), (256, 50), "Rayo", 13),  # sigue "AC" desde 466, que queda
    (3, (329, 107, 44, 18), (306, 60), "Fuego", 13),
    (4, (375, 107, 37, 18), (366, 52), "Hielo", 13),
    (1, (414, 107, 52, 18), (418, 48), "Aura", 13),
    (5, (146, 39, 64, 17), (146, 64), "Extra", 14),
    (6, (146, 56, 74, 17), (146, 82), "Evasión", 14),
    (7, (146, 73, 64, 17), (146, 80), "Defensa", 14),  # a la derecha, desde 227, hay otro gráfico
]
# "Hi- Critical" (índice 9) y "Critical" (índice 8, el final del mismo texto): "Súper Crítico" y "Crítico"
POPUP_CRITICAL = ((9, 8), (256, 54, 127, 18), ("Súper", "Crítico"), 13)
POPUP_TABLE = 0x37608


def _popup_alpha(text, cap, scale=4):
    """Texto en Arial Black inclinada (0-1) y su línea base."""
    from PIL import ImageDraw, ImageFont
    size = cap * scale
    while True:
        font = ImageFont.truetype(POPUP_FONT, size)
        box = font.getbbox("H")
        if box[3] - box[1] >= cap * scale:
            break
        size += 1
    big = Image.new("L", (font.getbbox(text)[2] + 8 * scale, size * 2), 0)
    ImageDraw.Draw(big).text((4 * scale, 0), text, font=font, fill=255)
    big = big.transform(big.size, Image.AFFINE, (1, POPUP_SLANT, -POPUP_SLANT * box[3], 0, 1, 0), Image.BICUBIC)
    small = np.array(big.resize((big.width // scale, big.height // scale), Image.BOX), float) / 255
    cols = np.nonzero(small.max(axis=0) > 0.05)[0]
    return small[:, cols[0]:cols[-1] + 1], box[3] / scale


def _popup_fit(alpha, width):
    """Angosta el texto (en el ancho) si no entra en `width` columnas."""
    if alpha.shape[1] <= width:
        return alpha
    img = Image.fromarray(np.round(alpha * 255).astype(np.uint8))
    return np.array(img.resize((width, alpha.shape[0]), Image.LANCZOS), float) / 255


def _popup_paint(alpha, baseline, h, base_row, fill):
    """Recorte de h filas: el texto con el degradé por fila y el borde oscuro."""
    top = base_row - round(baseline)
    a = np.zeros((h, alpha.shape[1] + 6))
    rows = alpha[max(0, -top):h - top]
    a[max(0, top):max(0, top) + rows.shape[0], 3:3 + alpha.shape[1]] = rows
    dist = _distance(a > 0.5, 4)
    border = np.clip(3 - dist, 0, 1) * 9
    return np.round(a * fill[:, None] + (1 - a) * border)


def _critical():
    """El texto de "Súper Crítico" y la columna donde empieza "Crítico" (el recorte corto)."""
    (_, _), (u, v, w, h), (first, second), cap = POPUP_CRITICAL
    a1, baseline = _popup_alpha(first, cap)
    a2, _ = _popup_alpha(second, cap)
    split = a1.shape[1] + 7  # un espacio
    alpha = np.zeros((max(a1.shape[0], a2.shape[0]), split + a2.shape[1]))
    alpha[:a1.shape[0], :a1.shape[1]] = a1
    alpha[:a2.shape[0], split:] = a2
    fitted = _popup_fit(alpha, w - 6)
    return fitted, baseline, round(split * fitted.shape[1] / alpha.shape[1])


OV01_CODE = {0x25AC8: (46, 52)}  # inmediatos de 16 bits del código (addiu a3 en 0xAA4AC8): ancho de "ENEMY"


def ov01_patches():
    """{posición en OV01.OVL: (antes, después)} de los u y anchos de los carteles que cambian."""
    rects = {index: (u, w, nu, nw) for index, (u, _, w, _), (nu, nw), _, _ in POPUPS if index is not None}
    (full, part), (u, _, w, _), _, _ = POPUP_CRITICAL
    split = _critical()[2]
    rects[part] = (290, 93, u + split, w - split)  # el borde de "Crítico" empieza 3 columnas antes: queda adentro
    return {POPUP_TABLE + 16 * i + 8 * k: (old, new) for i, (ou, ow, nu, nw) in rects.items()
            for k, (old, new) in enumerate(((ou, nu), (ow, nw))) if old != new}


def popups(sheet):
    img = np.array(sheet.view(8), float)
    boxes = [(rect, cap) for _, rect, _, _, cap in POPUPS] + [(POPUP_CRITICAL[1], POPUP_CRITICAL[3])]
    samples = {}  # alto de la mayúscula: por fila del recorte, los valores del relleno
    for (u, v, w, h), cap in boxes:
        for y in range(h):
            row = img[v + y, u:u + w]
            samples.setdefault(cap, {}).setdefault(y, []).extend(row[row > 0x60])
    fills = {cap: np.array([np.median(rows[y]) if rows.get(y) else 0 for y in range(20)]) for cap, rows in samples.items()}
    for (u, v, w, h), _ in boxes:
        img[v:v + h, u:u + w] = 0
    for _, (u, v, w, h), (nu, nw), text, cap in POPUPS:
        alpha, baseline = _popup_alpha(text, cap)
        cell = _popup_paint(_popup_fit(alpha, nw - 6), baseline, h, 16, fills[cap][:h])
        assert not img[v:v + h, nu:nu + nw].any(), f"{text!r}: el lugar no está libre"
        img[v:v + h, nu:nu + cell.shape[1]] = cell
    _, (u, v, w, h), _, cap = POPUP_CRITICAL
    alpha, baseline, _ = _critical()
    cell = _popup_paint(alpha, baseline, h, 16, fills[cap][:h])
    img[v:v + h, u:u + cell.shape[1]] = cell
    stat_labels(img)
    sheet.put(8, Image.fromarray(img.astype(np.uint8)))


# Rótulos chicos de la misma textura, con recortes fijos en el código de OV01 (inmediatos):
# - "PLAYER" y "ENEMY" (72 y 120, 157; 46 x 8): letra de 6 filas (0xEE, con la columna derecha de
#   los trazos en 0xCB y 0x2C en las diagonales) y un contorno 0x03 de un píxel. Quedan "ALIADO" y
#   "ENEMIGO" con letras de ese dibujo (las que no estaban, hechas igual).
# - "ZONE" (146, 106; 46 x 12): la E pasa a ser la A de "HP A B C", de la misma letra.
# - "MENU" (ficha de 36 x 17 en 704, 172): se le agrega la tilde a la U.
SIDE_LETTERS = {
    "A": ["....2ec", "...2eec", "..2ecec", ".2ec.ec", "2ec..ec", "ec...ec"],
    "L": ["ec....", "ec....", "ec....", "ec....", "ec....", "eeeeee"],
    "E": ["eeeeee", "ec....", "eeeeee", "ec....", "ec....", "eeeeee"],
    "N": ["eeeeeec"] + ["ec...ec"] * 5,
    "M": ["eeeeeeeec"] + ["ec..e..ec"] * 5,
    "I": ["ec"] * 6,
    "O": ["eeeeeec"] + ["ec...ec"] * 4 + ["eeeeeec"],
    "D": ["eeeeee.", "ec...ee", "ec...ec", "ec...ec", "ec...ee", "eeeeee."],
    "G": ["eeeeeec", "ec.....", "ec..eec", "ec...ec", "ec...ec", "eeeeeec"],
}
SIDE_TONES = {"e": 0xEE, "c": 0xCB, "2": 0x2C, "outline": 0x03}
SIDES = [((72, 157, 46, 8), "ALIADO"), ((120, 157, 52, 8), "ENEMIGO")]  # ENEMY tenía 46 de ancho
ZONE_A = ((146, 106, 46, 12), (180, 191), (176, 92, 12))  # ZONE, columnas de la E, la A de "HP A B C" (u, v, ancho)
MENU_ACCENT = (704 + 27, 172 + 3, [[0, 0xAA, 0xFF], [0xFF, 0xAA, 0]])  # tilde sobre la U (x, y, filas)


# "FRONT", "SELECT" y "BACK" sobre las flechas de la elección de zona: celdas de 46 x 38 en
# (72, 118 o 164; 186) (código de OV01 en 0xA89D30), la palabra en las filas 0-14 y la flecha
# debajo. Letra de 2 píxeles de trazo con un contorno oscuro; las letras nuevas se recortan de las
# tres palabras (núcleo > 0xB4 más una columna de contorno a cada lado, compartida con la vecina) y
# se angostan si no entran. SELECT queda (es el botón).
ZONE_CELLS = {"FRONT": 72, "SELECT": 118, "BACK": 164}
ZONE_TEXT = {"FRONT": "FRENTE", "BACK": "ATRÁS"}
ZONE_ROWS, ZONE_WIDTH, ZONE_INK = 15, 46, 0xB4
ZONE_ACCENT = [(0, 3), (0, 4), (1, 2), (1, 3)]  # (fila, columna desde el borde izquierdo de la A): la tilde


def zone_words(img):
    glyphs = {}
    for word, u in ZONE_CELLS.items():
        cell = img[186:186 + ZONE_ROWS, u:u + ZONE_WIDTH]
        for ch, (a, b) in zip(word, _runs((cell > ZONE_INK).any(axis=0))):
            glyphs.setdefault(ch, cell[:, a - 1:b + 1].copy())
    for word, text in ZONE_TEXT.items():
        parts = [glyphs[ACCENTED.get(ch, ch)].copy() for ch in text]
        while sum(p.shape[1] - 1 for p in parts) + 1 > ZONE_WIDTH - 2:
            k = max(range(len(parts)), key=lambda i: parts[i].shape[1])
            parts[k] = np.delete(parts[k], parts[k].shape[1] // 2, axis=1)
        out = np.zeros((ZONE_ROWS, sum(p.shape[1] - 1 for p in parts) + 1), int)
        x = 0
        for ch, p in zip(text, parts):
            out[:, x:x + p.shape[1]] = np.maximum(out[:, x:x + p.shape[1]], p)
            if ch in ACCENTED:
                for dy, dx in ZONE_ACCENT:
                    out[1 + dy, x + dx] = 0xFE
            x += p.shape[1] - 1
        u = ZONE_CELLS[word]
        img[186:186 + ZONE_ROWS, u:u + ZONE_WIDTH] = 0
        left = (ZONE_WIDTH - out.shape[1]) // 2
        img[186:186 + ZONE_ROWS, u + left:u + left + out.shape[1]] = out


def stat_labels(img):
    """img: la vista de 8 bits de stat.xtx (arreglo); rehace PLAYER/ENEMY, ZONE, MENU y la
    elección de zona."""
    zone_words(img)
    for (u, v, w, h), text in SIDES:
        ink = np.zeros((h, w), int)
        x = 1
        for ch in text:
            rows = SIDE_LETTERS[ch]
            for y, row in enumerate(rows):
                for k, c in enumerate(row):
                    if c in SIDE_TONES:
                        ink[1 + y, x + k] = SIDE_TONES[c]
            x += len(rows[0]) + 1
        assert x <= w, f"{text!r} no entra en {w}"
        outline = _near(ink > 0, 1.5) & (ink == 0)
        img[v:v + h, u:u + w] = np.where(outline, SIDE_TONES["outline"], ink)
    (u, v, w, h), (e0, e1), (au, av, aw) = ZONE_A
    img[v:v + h, e0:e1] = 0
    img[v:v + h, e0:e0 + aw] = np.maximum(img[v:v + h, e0:e0 + aw], img[av:av + h, au:au + aw])
    x, y, rows = MENU_ACCENT
    for dy, row in enumerate(rows):
        for dx, p in enumerate(row):
            img[y + dy, x + dx] = max(img[y + dy, x + dx], p)


def patch_ov01(data):
    """Aplica ov01_patches() (enteros de 32 bits) a OV01.OVL, después de comprobar el valor original."""
    data = bytearray(data)
    for pos, (old, new) in ov01_patches().items():
        assert struct.unpack_from("<i", data, pos)[0] == old, f"OV01.OVL: {pos:#x} no tiene {old}"
        struct.pack_into("<i", data, pos, new)
    for pos, (old, new) in OV01_CODE.items():
        assert struct.unpack_from("<H", data, pos)[0] == old, f"OV01.OVL: {pos:#x} no tiene {old}"
        struct.pack_into("<H", data, pos, new)
    return bytes(data)


# Rótulos de la ficha de estado (yosikawa/font.xtx, índices de 8 bits): el nítido usa los
# índices 0-15 y debajo se dibuja su resplandor, un desenfoque gaussiano del nítido.
FONT = "yosikawa/font.xtx"
LABEL_CELLS = {  # texto original: (celda del nítido, celda del resplandor)
    "HP": ((200, 432, 22, 20), (109, 411, 22, 20)), "EP": ((200, 452, 22, 20), (131, 411, 22, 20)),
    "C.Pt": ((447, 394, 31, 20), (159, 391, 31, 20)), "S.Pt": ((478, 394, 31, 20), (159, 411, 31, 20)),
    "Lv": ((327, 412, 20, 20), (111, 391, 20, 20)), "Next Lv": ((387, 428, 53, 20), (56, 411, 53, 20)),
    "Exp": ((340, 461, 28, 20), (131, 391, 28, 20)),
}
LABELS = {"C.Pt": "PC", "S.Pt": "PH", "Lv": "Nv", "Next Lv": "Sig. Nv"}  # como en los textos
GLOW_SIGMA, GLOW_GAIN = 2.0, 0.741  # ajustados sobre los siete rótulos originales
PAGE_ACCENT = [[0, 7, 15, 7], [7, 15, 7, 0]]  # tilde de la á de "Pág." (4 bits), filas 72-73
# Minúsculas de la fuente de 4 bits de la misma textura (misma familia que los rótulos):
# celdas de 9 x 14 desde (0, 14); su fila 14 cae en la fila 3 de la celda de un rótulo.
LOWER_CELL, LOWER_DY = (0, 14, 9, 14), 3


# Rótulos de 4 bits de la misma textura (vista de 4 bits; recortes del grupo 0): "NO DATA" en una
# letra fina y "Class", "Level", "Skill" y "Caster" en una gruesa de trazos de 2 píxeles (la de
# "Page"). Las letras se recortan de esas palabras (las separa una columna vacía) y las que faltan
# se dibujan con los mismos niveles (0-f), con la línea base en la fila 8 como las originales.
T4_WORDS = {  # texto original: (zona de las letras (u, v, ancho, alto), fila de la línea base, texto nuevo)
    "NO DATA": ((0, 91, 59, 10), 8, "SIN DATOS"),  # la fila 90 del recorte es de los números de arriba
    "Class": ((0, 101, 43, 9), 7, "Clase"),
    "Level": ((0, 110, 43, 11), 8, "Nivel"),
    "Skill": ((0, 120, 34, 11), 8, "Habil."),
    "Caster": ((0, 130, 54, 11), 8, "Usuario"),  # como en obj01
}
T4_WIDTH = {"NO DATA": 70, "Class": 44, "Skill": 41, "Caster": 62}  # ancho nuevo del recorte (EXE_PATCHES)
T4_LETTERS = {  # (palabra cuya letra imita, filas desde la 0, con la línea base en la 8)
    "S": ("NO DATA", ["", ".5dffe8.", "3fb44be6", "7f5.....", "3fd61...", ".6effd6.", "...16df3", ".....5f7",
                      "6eb44bf3", ".8effd5.", "..4762.."]),
    "I": ("NO DATA", ["", "4f4", "4f4", "4f4", "4f4", "4f4", "4f4", "4f4", "4f4", "4f4", "272"]),
    "N": ("Level", ["244...244", "7ffc..7ff", "7fffa.7ff", "7ffbf67ff", "7ff6fb7ff", "7ff.bfeff", "7ff..afff",
                    "7ff...cff", "1bf...1bf"]),
    "H": ("Level", ["244...244", "7ff...7ff", "7ff...7ff", "7ff...7ff", "7ffffffff", "7ffbbbbff", "7ff...7ff",
                    "7ff...7ff", "1bf...1bf"]),
    "U": ("Level", ["244...244"] + ["7ff...7ff"] * 6 + ["6ffa7aff6", "1bfffffb1"]),
    "b": ("Level", ["244.....", "7ff.....", "7ff4444.", "7ffffffb", "7ffa44ff", "7ff..7ff", "7ff..7ff",
                    "7ffc7bff", "7ffffffe"]),
    "o": ("Level", ["", "", "14444441", "8ffffff8", "ffa449ff", "ff7..7ff", "ff7..7ff", "ffc77bff", "7effffe7"]),
    "u": ("Level", ["", "", "442..244.", "ff7..7ff.", "ff7..7ff.", "ff7..7ff.", "ff7..7ff.", "ffc77bff4",
                    "7effffff7"]),
    ".": ("Level", ["", "", "", "", "", "", "", "ff", "ff"]),
}


def t4_labels(t4):
    """t4: la vista de 4 bits (0-15) como arreglo; rehace los rótulos de T4_WORDS en su lugar."""
    glyphs, words = {}, {}
    for word, ((u, v, w, h), base, _) in T4_WORDS.items():
        label = t4[v:v + h, u:u + w].copy()
        spans = _runs(label.any(axis=0))
        assert len(spans) == len(word.replace(" ", "")), f"{word}: {len(spans)} letras"
        words[word] = spans
        for ch, (a, b) in zip(word.replace(" ", ""), spans):
            glyphs.setdefault((word in ("NO DATA",), ch), (label[:, a:b], base))
    for ch, (like, rows) in T4_LETTERS.items():
        width = max(len(r) for r in rows)
        cell = np.array([[int(c, 16) if c != "." else 0 for c in r.ljust(width, ".")] for r in rows])
        glyphs[(like == "NO DATA", ch)] = (cell, 8)
    for word, ((u, v, w, h), base, text) in T4_WORDS.items():
        thin, gap = word == "NO DATA", 1  # una columna entre letras (la fina tenía 2: "SIN DATOS" no entraría)
        spans = words[word]
        space = max(b2[0] - b1[1] for b1, b2 in zip(spans, spans[1:]))  # el hueco del espacio, si hay
        out, x = np.zeros((h, 96), int), 0
        for ch in text:
            if ch == " ":
                x += space - gap
                continue
            g, b = glyphs[(thin, ch)]
            dy = base - b
            rows = g[max(0, -dy):h - dy]
            out[max(0, dy):max(0, dy) + rows.shape[0], x:x + g.shape[1]] |= rows
            x += g.shape[1] + gap
        width = x - gap
        assert width <= T4_WIDTH.get(word, w), f"{text!r}: {width} columnas"
        r0, r1 = _runs(t4[v:v + h, u:u + w].any(axis=1))[0]  # solo las filas de las letras: abajo hay otras
        assert not t4[v + r0:v + r1, u + w:u + width].any(), f"{text!r}: lo que se agrega no está libre"
        t4[v + r0:v + r1, u:u + max(w, width)] = out[r0:r1, :max(w, width)]


def font_xtx(sheet, read):
    img, t4 = sheet.view(8), sheet.view(4)
    font = {}
    for word, (cell, _) in LABEL_CELLS.items():
        for ch, g in cut_word(img, cell, word, edge=0).items():
            font.setdefault(ch, g)
    u0, v0, cw, ch_ = LOWER_CELL
    for ch in "ig":
        x = u0 + cw * (ord(ch) - ord("a"))
        g = t4.crop((x, v0, x + cw, v0 + ch_)).point(lambda p: p // 17)
        a, _, b, _ = g.getbbox()
        font[ch] = Glyph(g.crop((a, 0, b, ch_)), LOWER_DY, 0)
    for word, text in LABELS.items():
        cell, glow = LABEL_CELLS[word]
        draw(img, cell, text, font, left=4, gap=1, space=6)
        u, v, w, h = cell
        crisp = img.crop((u, v, u + w, v + h)).point(lambda p: p * 17)
        blur = crisp.filter(ImageFilter.GaussianBlur(GLOW_SIGMA)).point(lambda p: round(p * GLOW_GAIN))
        img.paste(blur, glow[:2])
    sheet.put(8, img)
    # "Page" de las páginas del GS Path (vista de 4 bits, recorte (108, 72, 39, 11)) -> "Pág.":
    # quedan la P, la a y la g; la a lleva tilde, la e se borra y va un punto
    t4 = np.array(sheet.view(4)) // 17
    t4[72:84, 137:148] = 0
    for (y, x), p in np.ndenumerate(np.array(PAGE_ACCENT)):
        t4[72 + y, 121 + x] = max(t4[72 + y, 121 + x], p)
    t4[79:81, 138:140] = 15
    t4_labels(t4)
    sheet.put(4, Image.fromarray((t4 * 17).astype(np.uint8)))


# Pestañas del menú principal (yosikawa/bg01.xtx, índices de 8 bits; recortes en la tabla del
# ejecutable, 0x2C9B82). Cada una ocupa una celda de 32 filas: la normal (letra clara con
# biselado, contorno oscuro y halo) y a su derecha la resaltada (la letra en negativo sobre una
# cápsula con trama). Las letras se recortan sin contorno; el contorno, el halo y la cápsula se
# rehacen para el texto nuevo.
BG01 = "yosikawa/bg01.xtx"
TAB_CELLS = {  # texto original: (u de la normal, v, ancho); la resaltada está en u + ancho
    "Items": (0, 0, 80), "Ether": (0, 32, 80), "Skills": (0, 64, 80), "Tech": (0, 96, 80),
    "Status": (0, 128, 80), "Party": (0, 160, 80), "U.M.N.": (160, 0, 96), "GS Path": (160, 32, 96),
    "Segment F": (160, 64, 96), "Options": (160, 96, 96),
}
TABS = {"Items": "Objetos", "Ether": "Éter", "Skills": "Habilid.", "Tech": "Técnicas",
        "Status": "Estado", "Party": "Grupo", "GS Path": "Ruta SG", "Segment F": "Segmentos",
        "Options": "Opciones"}  # U.M.N. queda
TAB_FILL = 120  # desde acá es letra (con su biselado); lo de alrededor depende de la distancia a ella
TAB_INK = 140  # en la resaltada solo cuenta desde acá (lo de 120 a 135 es borde que se pierde en la trama)
TAB_CAP = 12  # columnas de cada punta redondeada de la cápsula
TAB_MARGIN = 9  # mínimo entre el texto y el borde de la celda ("Segment F" deja 7, pero queda apretado)
# Letras que no están en las pestañas, en el mismo estilo: (fila de la celda donde empiezan, filas).
TAB_SHADES = {"f": 251, "e": 237, "d": 223, "b": 181, "a": 160, "9": 150, "7": 124, " ": 0}  # índices reales
TAB_LETTERS = {
    "b": (11, ["799", "bffa", "bffbaaa", "bfffffffa", "bffdbbffd", "bffa  ffe", "bffa  ffe",
               "bffebbffe", "bfffffffe", " aaaaaa9"]),
    "d": (11, ["      997", "     bffe", "  aaabffe", "bfffffffe", "dffbbdffe", "bffa  ffe", "bffa  ffe",
               "bffebbffe", "bfffffffe", " 9aaaaaa"]),
    "j": (12, ["   ffe", "   ffd", "", "   ffe", "   ffe", "   ffe", "   ffe", "   ffe", "bf ffd", "bffffa"]),
    "H": (12, ["bffa  ffe", "bffa  ffe", "bffa  ffe", "bfffffffe", "bfffffffe", "bffa  ffe", "bffa  ffe",
               "bffa  ffe", "79     97"]),
    "R": (12, ["bfffffff", "bffdbeffb", "bffa  ffe", "bffdbeffb", "bfffffffa", "bffbbffa", "bffa  ffe",
               "bffa   ff", "79     a9"]),  # la P con una pata en diagonal
    # las de las pestañas separan los trazos con tonos de biselado, que en las cápsulas quedan como letra
    "M": (12, ["ffffffffe", "ffffffffe", "ff ff ffe", "ff ff ffe", "ff ff ffe", "ff ff ffe", "ff ff ffe",
               "ff ff ffe", "9a 9a 9a"]),
    "m": (13, ["aaaaaaaa", "ffffffffe", "ff ff ffe", "ff ff ffe", "ff ff ffe", "ff ff ffe", "ff ff ffe",
               "9a 9a 9a"]),
    # copiadas de obj01 ("Attack Data", "Caster")
    "A": (12, [" bbffffff", " ffffbfff", "affb  bff", "affb  bff", "affb  bff", "affffffff", "afffbbbff",
               "bffb  bff", " bb    bb"]),
    "C": (12, [" fffffffb", "ffffbbfbb", "bff", "bffa", "bffa", "bffa", "bfffbbffb", " bffffffb", "  aaaabba"]),
    "D": (12, [" ffffffff", "bffbbbffb", "bffa  ffb", "bffa  ffb", "bffa  ffb", "bffa  ffb", "bffbbbffb",
               "fffffffb", " baaaaa"]),
    "L": (11, [" bbb", " bfff", "affb", "affb", "affb", "affb", "affb", " fffbbffb", "  bffffff", "    aaabb"]),
    "V": (12, ["bffa  ffe", "bffa  ffe", "bffa  ffe", "bffa  ffe", "bffb bffe", " fffbfff", " bfffffa", "  bfffa",
               "   aaa"]),
    "v": (14, ["bffa  ffe", "bffa  ffe", "bffb bffe", " fffbfff", " bfffffa", "  bfffa", "   aaa"]),
}
TAB_ACCENT = ["   bffa", "  bffa", " bffa"]  # tilde: empieza en la fila 7 sobre mayúscula, 9 sobre minúscula


def _shape(rows, top, height=32):
    w = max(len(r) for r in rows)
    out = np.zeros((height, w), int)
    for i, r in enumerate(rows):
        out[top + i, :len(r)] = [TAB_SHADES[c] for c in r]
    return out


def _distance(mask, limit=7):
    """Distancia euclídea de cada píxel al más cercano de `mask` (inf más allá de `limit`)."""
    out = np.full(mask.shape, np.inf)
    h, w = mask.shape
    for dy in range(-limit, limit + 1):
        for dx in range(-limit, limit + 1):
            d = (dy * dy + dx * dx) ** 0.5
            if d > limit:
                continue
            src = mask[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
            dst = out[max(0, dy):h - max(0, -dy), max(0, dx):w - max(0, -dx)]
            dst[src & (dst > d)] = d
    return out


def _near(mask, radius):
    """Píxeles a menos de `radius` de alguno de `mask`."""
    return _distance(mask, int(radius) + 1) <= radius


def _runs(cols):
    runs, start = [], None
    for i, c in enumerate(list(cols) + [False]):
        if c and start is None:
            start = i
        elif not c and start is not None:
            runs.append((start, i))
            start = None
    return runs


class Style:
    """Cómo se pinta una palabra de la fuente redondeada: qué índices toma cada tono de la letra
    (los de las pestañas) y cuáles los píxeles de alrededor, según la distancia a la letra (de a
    medio píxel). Se aprende de rótulos originales y se pinta con muestras al azar, que imitan la
    trama de los contornos."""

    def __init__(self):
        self.shade, self.bands = {}, {}

    def learn(self, fill, target, region):
        """fill: la palabra con los tonos de las pestañas, en su lugar; target: el rótulo original."""
        mask = fill > 0
        for a, b in zip(fill[mask & region], target[mask & region]):
            self.shade.setdefault(a, []).append(b)
        dist = np.round(_distance(mask) * 2) / 2
        around = region & ~mask & np.isfinite(dist)
        for d, b in zip(dist[around], target[around]):
            self.bands.setdefault(d, []).append(b)

    def paint(self, fill, rng):
        mask = fill > 0
        out = np.zeros(fill.shape, int)
        keys = np.array(sorted(self.shade))
        for y, x in zip(*np.nonzero(mask)):
            out[y, x] = rng.choice(self.shade[keys[np.abs(keys - fill[y, x]).argmin()]])
        dist = np.round(_distance(mask) * 2) / 2
        for d, values in self.bands.items():
            sel = (dist == d) & ~mask
            out[sel] = rng.choice(values, sel.sum())
        return out


def round_font(img):
    """Fuente redondeada de las pestañas de bg01 (vista de 8 bits): {letra: tonos en 32 filas},
    más lo que hace falta para rehacer cada pestaña: {pestaña: (relleno original, extremos)}."""
    font, tabs = {}, {}
    for word, (u, v, w) in TAB_CELLS.items():
        normal, high = img[v:v + 32, u:u + w], img[v:v + 32, u + w:u + 2 * w]
        fill = np.where(normal >= TAB_FILL, normal, 0)
        runs = _runs(fill.any(axis=0))
        assert len(runs) == len(word.replace(" ", "")), f"pestaña {word}: {len(runs)} letras"
        for (a, b), ch in zip(runs, word.replace(" ", "")):
            font.setdefault(ch, fill[:, a:b])
        cols = np.nonzero(high.any(axis=0))[0]
        tabs[word] = (fill, (runs[0][0], runs[-1][1], cols[0], cols[-1] + 1))
    for ch, (top, rows) in TAB_LETTERS.items():
        font[ch] = _shape(rows, top)
    font["q"] = font["p"][:, ::-1]
    accent = _shape(TAB_ACCENT, 0, 3)
    for ch, base, top in (("Á", "A", 7), ("É", "E", 7), ("Ó", "O", 7), ("Ú", "U", 7),
                          ("á", "a", 9), ("é", "e", 9), ("ó", "o", 9), ("ú", "u", 9)):
        g = font[base].copy()
        x = (g.shape[1] - accent.shape[1] + 1) // 2
        g[top:top + 3, x:x + accent.shape[1]] = np.maximum(g[top:top + 3, x:x + accent.shape[1]], accent)
        font[ch] = g
    return font, tabs


def compose(text, font, limit):
    """La palabra (32 filas, tonos de las pestañas) con una columna entre letras; si pasa de
    `limit` columnas, se angostan las letras más anchas de a una columna (menos la m, que tiene
    un trazo en la del medio)."""
    glyphs = [np.zeros((32, 3), int) if ch == " " else font[ch] for ch in text]
    while sum(g.shape[1] for g in glyphs) + len(glyphs) - 1 > limit:
        i = max((k for k in range(len(glyphs)) if text[k] not in "mM"), key=lambda k: glyphs[k].shape[1])
        assert glyphs[i].shape[1] > 7, f"{text!r} no entra en {limit} columnas"
        glyphs[i] = np.delete(glyphs[i], glyphs[i].shape[1] // 2, axis=1)
    out = np.zeros((32, sum(g.shape[1] for g in glyphs) + len(glyphs) - 1), int)
    x = 0
    for g in glyphs:
        out[:, x:x + g.shape[1]] = g
        x += g.shape[1] + 1
    return out


def pill_tones(label, old, tones=None):
    """Junta en `tones` (tonos de la letra, píxeles de fondo liso que la rodean) lo que muestra un
    rótulo original con la palabra `old` en su lugar."""
    shade, border = tones or ({}, [])
    ink = old >= TAB_INK
    for a, b in zip(old[ink], label[ink]):
        shade.setdefault(a, []).append(b)
    border += list(label[_near(ink, 1.5) & ~ink])
    return shade, border


def repill(label, old, new, cols, cap, rng, tones=None, clear=2):
    """Rehace un rótulo que es una palabra sobre una cápsula con trama: `old` y `new` son la palabra
    original y la nueva en su lugar (tonos de las pestañas) y `cols`, las columnas que se tocan. Los
    tonos de la letra y el fondo liso que la rodea salen de `tones` o del mismo rótulo; la cápsula,
    sin el texto viejo (lo que está a `clear` píxeles de él), se estira o se achica por el medio y
    conserva su corrimiento respecto del texto."""
    lo, hi = cols
    out = label.copy()
    ink, new_ink = old >= TAB_INK, new >= TAB_INK
    shade, border = tones or pill_tones(label, old)
    span = np.nonzero(label[:, lo:hi].any(axis=0))[0]
    pa, pb = lo + span[0], lo + span[-1] + 1
    oa, ob = np.nonzero(ink.any(axis=0))[0][[0, -1]] + (0, 1)
    na, nb = np.nonzero(new_ink.any(axis=0))[0][[0, -1]] + (0, 1)
    # la cápsula sin el texto: cada píxel tapado toma uno libre del medio de la misma fila; en las
    # filas del texto no queda ninguno y va el fondo liso que hay entre letras
    clean, hole = label.copy(), _near(old > 0, clear)
    text_rows = np.nonzero((old > 0).any(axis=1))[0]
    hole[:text_rows[0] - 1] = hole[text_rows[-1] + 2:] = False  # el borde de arriba y de abajo queda
    x = np.arange(label.shape[1])
    inner = (x >= pa + cap) & (x < pb - cap)
    for y in range(label.shape[0]):
        free = clean[y][inner & ~hole[y]]
        todo = hole[y] & (x >= pa) & (x < pb)
        if todo.any():
            clean[y, todo] = rng.choice(free, todo.sum()) if len(free) else np.bincount(border).argmax()
    size = min(hi - lo, (nb - na) + (pb - pa) - (ob - oa))
    middle = clean[:, pa + cap:pb - cap]
    reps = -(-(size - 2 * cap) // middle.shape[1])
    capsule = np.hstack([clean[:, pa:pa + cap], np.tile(middle, reps)[:, :size - 2 * cap], clean[:, pb - cap:pb]])
    left = min(max(lo, round((na + nb) / 2 + (pa + pb - oa - ob) / 2 - size / 2)), hi - size)
    out[:, lo:hi] = 0
    out[:, left:left + size] = capsule
    edge = _near(new_ink, 1.5) & ~new_ink
    out[edge] = np.bincount(border).argmax()  # el más común, como el original
    keys = np.array(sorted(shade))
    mode = {k: np.bincount(shade[k]).argmax() for k in keys}  # el más común: la letra queda nítida
    for y, x in zip(*np.nonzero(new_ink)):
        out[y, x] = mode[keys[np.abs(keys - new[y, x]).argmin()]]
    return out


def bg01(sheet, read):
    img = np.array(sheet.view(8), int)
    font, tabs = round_font(img)
    style = Style()
    for word, (u, v, w) in TAB_CELLS.items():
        style.learn(tabs[word][0], img[v:v + 32, u:u + w], np.ones((32, w), bool))
    for word, text in TABS.items():
        u, v, w = TAB_CELLS[word]
        old, (fa, fb, _, _) = tabs[word]
        rng = np.random.default_rng(zlib.crc32(text.encode()))
        word_fill = compose(text, font, w - 2 * TAB_MARGIN)
        fill = _place(word_fill, (32, w), round((fa + fb - word_fill.shape[1]) / 2), 0)  # centrado como el original
        high = img[v:v + 32, u + w:u + 2 * w]
        img[v:v + 32, u + w:u + 2 * w] = repill(high, old, fill, (0, w), TAB_CAP, rng)  # en negativo
        img[v:v + 32, u:u + w] = style.paint(fill, rng)
    sheet.put(8, Image.fromarray(img.astype(np.uint8)))


# Rótulos de las pantallas del menú (yosikawa/obj01.xtx, índices de 8 bits; recortes en la tabla
# del ejecutable desde 0x2C9EB2). Misma fuente que las pestañas, con otros tonos y un halo
# punteado; los de las listas llevan "<<" y ">>" (20 columnas a cada lado), que quedan. Como el
# juego dibuja cada recorte con su ancho, los textos largos se abrevian para que entren.
OBJ01 = "yosikawa/obj01.xtx"
# {palabra original: ((u, v, ancho, alto) del recorte, (desde, hasta) columnas de la cápsula, texto)}
# Los de las listas llevan "<<" y ">>" (20 columnas a cada lado), que quedan.
OBJ_LABELS = {
    "Items": ((369, 149, 90, 20), (20, 70), "Obj."), "Ether": ((369, 169, 94, 20), (20, 74), "Éter"),
    "Skills": ((369, 189, 93, 20), (20, 73), "Habil."), "Party": ((369, 209, 94, 20), (20, 74), "Grupo"),
    "Equip": ((369, 229, 93, 20), (20, 73), "Equip."), "Attack Data": ((157, 259, 146, 20), (20, 126), "Datos"),
    "Learned": ((303, 259, 117, 20), (20, 97), "Aprend."), "Accessories": ((0, 489, 152, 20), (20, 132), "Accesorios"),
    "Caster": ((152, 489, 64, 18), (0, 64), "Usuario"),
}
PILL_CAP = 8  # columnas de cada punta de la cápsula de la palabra
PILL_INSET = 2  # mínimo entre la letra y el borde de la cápsula
OBJ_INK = 158  # en obj01, desde acá es letra (debajo, el contorno claro de 144-154)


def _match(fill, target):
    """Dónde cae la palabra `fill` (32 filas) dentro del rótulo `target`: corrimiento (dx, dy)."""
    mask = fill > 0
    ys, xs = np.nonzero(mask)
    tpl = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    bright = target >= OBJ_INK
    best = None
    for dy in range(0, target.shape[0] - tpl.shape[0] + 1):
        for dx in range(0, target.shape[1] - tpl.shape[1] + 1):
            score = (bright[dy:dy + tpl.shape[0], dx:dx + tpl.shape[1]] == tpl).mean()
            if best is None or score > best[0]:
                best = (score, dx - xs.min(), dy - ys.min())
    return best[1], best[2]


def _place(word_fill, shape, x, dy):
    out = np.zeros(shape, int)
    ys, xs = np.nonzero(word_fill)
    keep = (ys + dy >= 0) & (ys + dy < shape[0])
    out[ys[keep] + dy, xs[keep] + x] = word_fill[ys[keep], xs[keep]]
    return out


def relabel(img, font, tabs, labels, tones=None):
    """Rehace los rótulos de cápsula de una textura (labels como OBJ_LABELS). La palabra original
    sale de la pestaña si está (mismo espaciado) o se arma con la fuente; sin `tones`, los tonos
    se aprenden de los mismos rótulos."""
    found = {}
    for word, ((u, v, w, h), (lo, hi), text) in labels.items():
        label = img[v:v + h, u:u + w]
        if word in tabs or all(ch in font or ch == " " for ch in word):
            original = tabs[word][0] if word in tabs else compose(word, font, 999)
            dx, dy = _match(original, label)
            found[word] = (_place(original, label.shape, dx, dy), dy)
        else:  # faltan letras: la palabra vieja son los trazos claros de la cápsula (los de 2 px
            # o más de grueso; el borde punteado es de 1)
            ink = np.zeros(label.shape, bool)
            ink[4:h - 4, lo + 2:hi - 2] = label[4:h - 4, lo + 2:hi - 2] >= OBJ_INK
            block = ink[:-1, :-1] & ink[1:, :-1] & ink[:-1, 1:] & ink[1:, 1:]
            strokes = np.zeros_like(ink)
            for dy_, dx_ in ((0, 0), (1, 0), (0, 1), (1, 1)):
                strokes[dy_:dy_ + block.shape[0], dx_:dx_ + block.shape[1]] |= block
            rows = np.nonzero(strokes.any(axis=1))[0]
            found[word] = (np.where(strokes, TAB_SHADES["f"], 0), rows[0] - 12)  # fila 12: arriba de la mayúscula
    if tones is None:
        for word, ((u, v, w, h), _, _) in labels.items():
            tones = pill_tones(img[v:v + h, u:u + w], found[word][0], tones)
    for word, ((u, v, w, h), (lo, hi), text) in labels.items():
        label = img[v:v + h, u:u + w]
        old, dy = found[word]
        rng = np.random.default_rng(zlib.crc32(text.encode()))
        oa, ob = np.nonzero(old.any(axis=0))[0][[0, -1]] + (0, 1)
        inset = max(0, min(PILL_INSET, oa - lo, hi - ob))  # no más que lo que deja el original
        word_fill = compose(text, font, hi - lo - 2 * inset)
        center = (np.nonzero(old.any(axis=0))[0][[0, -1]].sum() + 1) / 2  # centrado como el original
        new = _place(word_fill, label.shape, round(center - word_fill.shape[1] / 2), dy)
        img[v:v + h, u:u + w] = repill(label, old, new, (lo, hi), PILL_CAP, rng, tones, 2 if word in tabs else 3)
    return tones


def obj01_tones(read, font, tabs):
    """Tonos de los rótulos de cápsula: de las cuatro palabras que están en obj01 y en las
    pestañas, con el mismo espaciado. Sirven también para g2_01 y seg01 (mismo estilo)."""
    img = np.array(Sheet(read(OBJ01)).view(8), int)
    return relabel(img, font, tabs, {w: OBJ_LABELS[w] for w in ("Items", "Ether", "Skills", "Party")})


def obj01(sheet, read):
    img = np.array(sheet.view(8), int)
    font, tabs = round_font(np.array(Sheet(read(BG01)).view(8), int))
    relabel(img, font, tabs, OBJ_LABELS, obj01_tones(read, font, tabs))
    banners(img)
    sheet.put(8, Image.fromarray(img.astype(np.uint8)))


# Pantallas del GS Path (yosikawa/g2_01.xtx) y de los Segment Files (yosikawa/seg01.xtx): rótulos
# de cápsula como los de obj01 (recortes en la tabla del ejecutable: grupos 5 y 6, desde 0x2CA7F0).
G2_01 = "yosikawa/g2_01.xtx"
G2_LABELS = {
    "Entrance": ((0, 237, 129, 20), (17, 110), "Entrada"),  # entre dos estrellas
    "Result": ((129, 237, 59, 20), (0, 59), "Logros"),
    "Citizen Profile": ((0, 257, 130, 20), (0, 130), "Ciudadano"),
    "Exit": ((130, 257, 39, 20), (0, 39), "Salir"),
    "Message from Client": ((0, 277, 177, 20), (0, 177), "Mensaje del cliente"),
    "Message from Procurator": ((0, 297, 226, 20), (0, 226), "Mensaje del procurador"),
    "Back": ((198, 241, 68, 20), (21, 68), "Atrás"),  # después de "<<"
    "Next": ((316, 287, 64, 20), (0, 45), "Sig."),  # antes de ">>"
}
SEG01 = "yosikawa/seg01.xtx"
SEG_LABELS = {
    "Segment Address": ((0, 219, 151, 20), (0, 151), "Dirección"),
    "Treasure Details": ((339, 200, 151, 20), (0, 151), "Datos del tesoro"),
}


# Los dos botones de la entrada del GS Path, en dos tamaños (seleccionado y no): texto suavizado
# de 16 niveles en una fuente geométrica; se rehacen con Century Gothic.
G2_BUTTONS = {  # recorte: (texto, fila de arriba de la mayúscula, alto de la mayúscula)
    (0, 317, 100, 15): ("Logros", 1, 12), (100, 317, 100, 15): ("Logros", 3, 10),
    (200, 317, 117, 15): ("Ciudadanos", 1, 12), (317, 317, 117, 15): ("Ciudadanos", 3, 10),
}
BUTTON_FONT = "C:/Windows/Fonts/GOTHIC.TTF"


def render_text(text, cap, path=BUTTON_FONT, scale=4):
    """Texto suavizado (0-15) con la mayúscula de `cap` píxeles: se dibuja a `scale` veces el
    tamaño y se reduce promediando. Devuelve (imagen, fila donde empieza la mayúscula)."""
    from PIL import ImageDraw, ImageFont
    size = cap * scale
    while True:
        font = ImageFont.truetype(path, size)
        top, bottom = font.getbbox("H")[1], font.getbbox("H")[3]
        if bottom - top >= cap * scale:
            break
        size += 1
    big = Image.new("L", (font.getbbox(text)[2] + 2 * scale, size * 2), 0)
    ImageDraw.Draw(big).text((scale, 0), text, font=font, fill=255)
    small = big.resize((big.width // scale, big.height // scale), Image.BOX)
    out = np.array(small, int) * 15 // max(1, np.array(small).max())
    cols = np.nonzero(out.any(axis=0))[0]
    return out[:, cols[0]:cols[-1] + 1], top // scale


# Cartel "GS PATH": dos cápsulas con trama y letras de bloque de 9 columnas (filas 11 a 20). Queda
# "RUTA SG": el cartel se espeja para que la cápsula de cuatro letras quede a la izquierda y en cada
# lugar se pega una letra entera, con su contorno y la trama de sus huecos. La R es la panza de la P
# con las patas de la A; la U, la H sin el travesaño y cerrada abajo.
G2_HEADER = (177, 266, 117, 31)
HEADER_LETTERS = {"G": 11, "S": 26, "P": 52, "A": 67, "T": 82, "H": 97}  # columna de cada letra
HEADER_TEXT = "RUTASG"  # en los lugares que quedan al espejar, de izquierda a derecha
HEADER_ROWS = (11, 21)


def g2_header(img):
    u, v, w, h = G2_HEADER
    label = img[v:v + h, u:u + w]
    top, bottom = HEADER_ROWS
    cell = {ch: label[top:bottom, x:x + 9].copy() for ch, x in HEADER_LETTERS.items()}
    p, a, hh = cell["P"], cell["A"], cell["H"]
    cell["R"] = np.vstack([p[:6], a[7:9], a[8:10]])
    base = hh[9].copy()
    base[3:6] = base[[2, 1, 2]]  # el borde de abajo sigue bajo el travesaño
    cell["U"] = np.vstack([hh[:4], hh[6:9], hh[4:6], base])
    out = label[:, ::-1].copy()
    slots = sorted(w - x - 9 for x in HEADER_LETTERS.values())
    for x, ch in zip(slots, HEADER_TEXT):
        out[top:bottom, x:x + 9] = cell[ch]
    img[v:v + h, u:u + w] = out


def g2_01(sheet, read):
    img = np.array(sheet.view(8), int)
    font, tabs = round_font(np.array(Sheet(read(BG01)).view(8), int))
    relabel(img, font, tabs, G2_LABELS, obj01_tones(read, font, tabs))
    g2_header(img)
    for (u, v, w, h), (text, cap_top, cap) in G2_BUTTONS.items():
        glyphs, top = render_text(text, cap)
        y0 = cap_top - top
        x0 = (w - glyphs.shape[1]) // 2
        cell = np.zeros((h, w), int)
        rows = glyphs[max(0, -y0):h - y0]
        cell[max(0, y0):max(0, y0) + rows.shape[0], x0:x0 + glyphs.shape[1]] = rows
        img[v:v + h, u:u + w] = cell
    sheet.put(8, Image.fromarray(img.astype(np.uint8)))


# Los estados de cada archivo: una letra por baldosa redondeada. Las baldosas se recortan por el
# borde de arriba (fila 1, donde no se tocan) y se vuelven a acomodar.
SEG_TILES = {  # texto original: recorte
    "NO DATA": (0, 129, 112, 18), "IN PROGRESS": (0, 147, 152, 18), "COMPLETE!!": (0, 165, 152, 18),
}
SEG_STATES = {"NO DATA": "SIN DATOS", "IN PROGRESS": "PENDIENTE", "COMPLETE!!": "¡COMPLETO!"}  # "EN PROGRESO" no entra
SEG_SPACE = 8  # columnas vacías entre palabras
# "SIN DATOS" no entra en los 112 de "NO DATA": el recorte se ensancha en el ejecutable (los otros
# dos estados, en el mismo lugar de la pantalla, miden 152; en la textura hay lugar hasta 136).
SEG_WIDTH = {"NO DATA": 136}
# Cartel "SEGMENT FILE": once baldosas sueltas de 17 x 18 que el ejecutable dibuja de a una, cada 35
# columnas de pantalla (0x2336A0). Queda "SEGMENTOS": las de F e I pasan a ser O y S (del abecedario
# de baldosas de la misma textura) y se corren para seguir a la T; las de L y E quedan vacías.
SEG_HEADER_TILES = [(0, 201, "O"), (17, 201, "S"), (34, 201, None), (51, 201, None)]  # las de "FILE"
SEG_ALPHABET = (256, 220, 18)  # A-M en esta fila y N-Z en la de abajo, una baldosa cada 18
EXE_PATCHES = {  # u16 en el ejecutable: (antes, después)
    0x2CB3B6: (112, 136),  # ancho del recorte de "NO DATA" (grupo 6, 0x2CB3B0)
    0x114738: (335, 304), 0x11474C: (370, 339),  # x de las baldosas 8 y 9 del cartel (addiu a1)
    0x2CBC76: (47, 48),  # ancho del recorte de "NEW!" (grupo 10, 0x2CBC70): "NUEVA" no entra en 47
    # anchos de los rótulos de 4 bits de font.xtx (grupo 0): "SIN DATOS", "Clase", "Habil.", "Usuario"
    0x2C90D6: (59, 70), 0x2C96F6: (43, 44), 0x2C9106: (34, 41), 0x2C9316: (54, 62),
}


# Cartel "LOAD" / "SAVE" de la pantalla de cargar y guardar: cuatro baldosas del abecedario de
# seg01 (recortes 640-665 = A-Z) en x 335, 370, 405 y 440 (código en 0x239514, una llamada por letra
# que elige entre las dos palabras según un byte en gp-21472: 0 = guardar). Para "CARGAR" y
# "GUARDAR" ese bloque de 33 instrucciones se reemplaza por un bucle que dibuja las letras de una
# lista, alineadas a la derecha como el original; al final deja s0 y s1 como el código que sigue.
SAVE_LOAD_CODE = 0x239514  # dirección del bloque (vaddr; en el archivo, - 0x11F000)
SAVE_LOAD_WORDS = {"save": "GUARDAR", "load": "CARGAR"}
SAVE_LOAD_ORIGINAL = "20 ac 83 93 92 02 02 24 8b 02 04 24 4f 01 05 24"  # primeros 16 bytes, para comprobar


def save_load_code():
    """(posición en el ejecutable, bytes originales, bytes nuevos) del bloque."""
    pc0 = SAVE_LOAD_CODE
    r = {"zero": 0, "v1": 3, "a0": 4, "a1": 5, "a2": 6, "a3": 7, "s0": 16, "s1": 17, "s4": 20, "s5": 21, "gp": 28}

    def i_type(op, rs, rt, imm):
        return (op << 26) | (r[rs] << 21) | (r[rt] << 16) | (imm & 0xFFFF)

    words, labels, fixups = [], {}, []

    def emit(word):
        words.append(word)

    def branch(rs, rt, label):
        fixups.append((len(words), label))
        emit(i_type(4, rs, rt, 0))

    tables = {k: [640 + ord(c) - 65 for c in w] + [0] for k, w in SAVE_LOAD_WORDS.items()}
    end_x = 440  # la última letra, donde estaba la D o la E
    code_len = 19
    table_at = pc0 + 4 * code_len
    save_table, load_table = table_at, table_at + 2 * len(tables["save"])
    emit(i_type(0x24, "gp", "v1", -21472))                        # lbu v1, -21472(gp)
    emit(i_type(0x0F, "zero", "s1", (save_table + 0x8000) >> 16))  # lui s1, (lista de guardar; el addiu suma con signo)
    emit(i_type(0x09, "s1", "s1", save_table & 0xFFFF))           # addiu s1, s1, ...
    branch("v1", "zero", "loop")                                  # beq v1, zero, loop
    emit(i_type(0x09, "zero", "s0", end_x - 35 * (len(tables["save"]) - 2)))  # (retardo) x inicial
    emit(i_type(0x09, "s1", "s1", load_table - save_table))       # addiu s1, s1, (lista de cargar)
    emit(i_type(0x09, "zero", "s0", end_x - 35 * (len(tables["load"]) - 2)))
    labels["loop"] = len(words)
    emit(i_type(0x25, "s1", "a0", 0))                             # lhu a0, 0(s1)
    branch("a0", "zero", "done")                                  # beq a0, zero, done
    emit((r["s0"] << 21) | (r["zero"] << 16) | (r["a1"] << 11) | 0x2D)  # (retardo) daddu a1, s0, zero
    emit(i_type(0x09, "zero", "a2", 13))                          # addiu a2, zero, 13
    emit((3 << 26) | (0x21A758 >> 2))                             # jal 0x21a758 (dibuja un recorte)
    emit(i_type(0x09, "zero", "a3", 1))                           # (retardo) addiu a3, zero, 1
    emit(i_type(0x09, "s1", "s1", 2))                             # addiu s1, s1, 2
    branch("zero", "zero", "loop")                                # b loop
    emit(i_type(0x09, "s0", "s0", 35))                            # (retardo) addiu s0, s0, 35
    labels["done"] = len(words)
    emit(i_type(0x09, "s4", "s1", -18792))                        # addiu s1, s4, -18792 (como el original)
    labels["after"] = 33
    branch("zero", "zero", "after")                               # b 0x239598
    emit(i_type(0x09, "s5", "s0", -12824))                        # (retardo) addiu s0, s5, -12824
    assert len(words) == code_len
    for k, label in fixups:
        words[k] |= (labels[label] - k - 1) & 0xFFFF
    halves = tables["save"] + tables["load"]
    halves += [0] * (len(halves) % 2)
    body = struct.pack(f"<{len(words)}I", *words) + struct.pack(f"<{len(halves)}H", *halves)
    assert len(body) <= 4 * 33, "el bucle no entra en el bloque"
    body += bytes(4 * 33 - len(body))  # el resto no se ejecuta (el último salto va a 0x239598)
    return pc0 - 0x11F000, bytes.fromhex(SAVE_LOAD_ORIGINAL), body


def _tiles(img, rect, word):
    """{letra: baldosa} y el ancho de un espacio en un rótulo de baldosas."""
    u, v, w, h = rect
    label = img[v:v + h, u:u + w]
    letters = word.replace(" ", "")
    spans = None
    for y in list(range(4)) + list(range(h - 4, h)):
        runs = _runs(label[y] > 0)
        if len(runs) == len(letters) - 1 and word.endswith("!!"):  # "!!" en una sola baldosa
            a, b = runs[-1]
            runs[-1:] = [(a, (a + b) // 2), ((a + b) // 2, b)]
        if len(runs) == len(letters):
            spans = runs
            break
    assert spans, f"{word}: no hay una fila que separe las baldosas"
    edges = [0] + [(spans[k][1] + spans[k + 1][0]) // 2 for k in range(len(spans) - 1)] + [w]
    tiles = {}
    for k, ch in enumerate(letters):
        tile = label[:, edges[k]:edges[k + 1]]
        cols = np.nonzero(tile.any(axis=0))[0]
        tiles.setdefault(ch, tile[:, cols[0]:cols[-1] + 1].copy())
    return tiles, int(np.nonzero(label.any(axis=0))[0][0])


def seg01(sheet, read):
    img = np.array(sheet.view(8), int)
    font, tabs = round_font(np.array(Sheet(read(BG01)).view(8), int))
    relabel(img, font, tabs, SEG_LABELS, obj01_tones(read, font, tabs))
    found = {word: _tiles(img, rect, word) for word, rect in SEG_TILES.items()}
    gray = {**found["NO DATA"][0], **found["IN PROGRESS"][0]}
    white = dict(found["COMPLETE!!"][0])
    white["¡"] = white["!"][::-1]
    u0, v0, step = SEG_ALPHABET
    for u, v, ch in SEG_HEADER_TILES:
        if ch is None:
            img[v:v + 18, u:u + 17] = 0
            continue
        k = ord(ch) - ord("A")
        a, b = u0 + k % 13 * step, v0 + k // 13 * step
        img[v:v + 18, u:u + 17] = img[b:b + 18, a:a + 17]
    for word, text in SEG_STATES.items():
        u, v, w, h = SEG_TILES[word]
        w = SEG_WIDTH.get(word, w)
        start = found[word][1]
        source = white if word == "COMPLETE!!" else gray
        out = np.zeros((h, w), int)
        x = start
        for ch in text:
            if ch == " ":
                x += SEG_SPACE
                continue
            t = source[ch]
            assert x + t.shape[1] <= w, f"{text!r} no entra"
            out[:, x:x + t.shape[1]] = np.maximum(out[:, x:x + t.shape[1]], t)
            x += t.shape[1]
        img[v:v + h, u:u + w] = out
    sheet.put(8, Image.fromarray(img.astype(np.uint8)))


# Estados de la Ruta SG (yosikawa/g2_02.xtx, índices de 8 bits; recortes en el grupo 10 de la
# tabla del ejecutable, desde 0x2CBBF0). Letras de 8 x 12 con trazos de 2 píxeles, a 3 columnas
# una de otra, en tres estilos: planas sobre una trama que se repite cada 11 columnas (SUCCEEDED!,
# NEW!), oscuras con sombra sobre una placa en degradé (FAILED!) y blancas, cada palabra con su
# placa ajustada a las letras (IN PROGRESS, NO DATA). En los dos últimos, la palabra nueva se arma
# con letras enteras del mismo estilo (con su placa y su sombra); en las planas, con la forma de
# cualquier letra sobre la trama sin letras. Van en femenino, como la Ruta n.º 01 a la que se
# refieren (la ayuda de esa pantalla está en el ejecutable, 0x2CD9A8).
G2_02 = "yosikawa/g2_02.xtx"
G2_WORDS = {  # texto original: (recorte, tono de la letra, texto nuevo)
    "SUCCEEDED!": ((0, 0, 118, 22), 0x9D, "¡LOGRADA!"),
    "FAILED!": ((118, 0, 118, 22), 0x01, "¡FALLIDA!"),
    "IN PROGRESS": ((0, 22, 118, 22), 0xF9, "PENDIENTE"),
    "NO DATA": ((118, 22, 118, 22), 0xF9, "SIN DATOS"),
    "NEW!": ((184, 80, 48, 20), 0x9D, "NUEVA"),  # 47 de ancho en el original: ver EXE_PATCHES
}
G2_FLAT = ("SUCCEEDED!", "NEW!")
G2_PERIOD = 11  # la trama de las letras planas
G2_SPACING = {"NEW!": (1, 2)}  # (columnas entre letras, entre la placa y la letra); en el resto (3, 4)
G2_PLATE_GAP = 2  # entre las placas de dos palabras
LETTER_V = ["##....##"] * 6 + [".##..##."] * 2 + ["..####.."] * 2 + ["...##..."] * 2
# El globo "OPEN :" de los mensajes (antes del botón ○): letra condensada de 9 píxeles de alto,
# suavizada, con una sombra un píxel abajo a la derecha, sobre un fondo liso.
G2_OPEN = ((0, 102, 76, 22), (23, 3, 60, 15), (25, 13), "ABRIR :")  # recorte, texto viejo, (x, línea base), texto
OPEN_FONT = ("C:/Windows/Fonts/bahnschrift.ttf", 13, b"Bold Condensed")
OPEN_TONES = (0x1A, 0x83, 0x46)  # fondo, letra, sombra


def _g2_flat(label, mask, plate, text, shapes, tone, gap, margin):
    """Palabra plana: la trama sin las letras viejas (cada píxel tapado se copia de la misma fila,
    un período más allá; donde todas las letras tienen trazo, de un píxel libre de la fila), con
    un tramo del medio de menos o de más, y las letras nuevas encima."""
    p0, p1 = plate
    clean, todo = label.copy(), mask.copy()
    for y, x in zip(*np.nonzero(mask)):
        for k in (1, -1, 2, -2, 3, -3, 4, -4):
            x2 = x + G2_PERIOD * k
            if p0 < x2 < p1 - 1 and not mask[y, x2]:
                clean[y, x], todo[y, x] = label[y, x2], False
                break
    rng = np.random.default_rng(zlib.crc32(text.encode()))
    for y in np.nonzero(todo.any(axis=1))[0]:
        free = label[y, p0 + 2:p1 - 2][~mask[y, p0 + 2:p1 - 2]]
        clean[y][todo[y]] = rng.choice(free, todo[y].sum())
    glyphs = [shapes[ch] for ch in text]
    inner = sum(g.shape[1] for g in glyphs) + gap * (len(glyphs) - 1)
    body = clean[:, p0:p1]
    n = body.shape[1]
    if inner + 2 * margin < n:  # se saca de a períodos enteros, para que la trama siga
        cut = (n - inner - 2 * margin) // G2_PERIOD * G2_PERIOD
        body = np.delete(body, range((n - cut) // 2, (n + cut) // 2), axis=1)
    elif inner + 2 * margin > n:
        extra, c = inner + 2 * margin - n, n // 2
        body = np.hstack([body[:, :c], body[:, c - extra:c], body[:, c:]])
    top = np.nonzero(mask.any(axis=1))[0][0]
    x = (body.shape[1] - inner) // 2
    for g in glyphs:
        body[top:top + 12, x:x + g.shape[1]][g] = tone
        x += g.shape[1] + gap
    return body


def g2_02(sheet, read):
    img = np.array(sheet.view(8), int)
    sources, shapes, cells, caps = {}, {"V": np.array([[c == "#" for c in r] for r in LETTER_V])}, {}, {}
    for word, ((u, v, w, h), tone, _) in G2_WORDS.items():
        label = img[v:v + h, u:u + w].copy()
        mask = label == tone
        spans, plates = _runs(mask.any(axis=0)), _runs((label > 0).any(axis=0))
        assert len(spans) == len(word.replace(" ", "")), f"{word}: {len(spans)} letras"
        sources[word] = label, mask, plates
        top = np.nonzero(mask.any(axis=1))[0][0]
        for ch, (a, b) in zip(word.replace(" ", ""), spans):
            shapes.setdefault(ch, mask[top:top + 12, a:b])
            cells.setdefault((tone, ch), label[:, a - 1:b + 2])  # con la mitad de cada separación
        p0, p1 = plates[-1]
        caps.setdefault(tone, (label[:, p0:spans[-len(word.split(" ")[-1])][0] - 1], label[:, spans[-1][1] + 2:p1]))
    shapes["¡"] = shapes["!"][::-1]
    for (tone, ch), cell in list(cells.items()):
        if ch == "!":
            cells[(tone, "¡")] = cell[::-1]
    for word, ((u, v, w, h), tone, text) in G2_WORDS.items():
        label, mask, plates = sources[word]
        if word in G2_FLAT:
            gap, margin = G2_SPACING.get(word, (3, 4))
            new = _g2_flat(label, mask, plates[0], text, shapes, tone, gap, margin)
        else:
            left, right = caps[tone]
            pieces = []
            for part in text.split(" "):
                if pieces:
                    pieces.append(np.zeros((h, G2_PLATE_GAP), int))
                pieces += [left] + [cells[(tone, ch)] for ch in part] + [right]
            new = np.hstack(pieces)
        assert new.shape[1] <= w, f"{text!r} no entra en {w} columnas"
        img[v:v + h, u:u + w] = 0
        x = (w - new.shape[1]) // 2
        img[v:v + h, u + x:u + x + new.shape[1]] = new
    (u, v, w, h), (x0, y0, x1, y1), (tx, base), text = G2_OPEN
    path, size, variation = OPEN_FONT
    background, ink, shadow = OPEN_TONES
    pill = img[v:v + h, u:u + w].astype(float)
    pill[y0:y1, x0:x1] = background
    alpha, baseline = text_mask(text, path, size, variation=variation)
    assert tx + alpha.shape[1] + 1 < w - 4, f"{text!r} no entra"
    top = base - round(baseline)
    for d, tone in ((1, shadow), (0, ink)):
        layer = np.zeros_like(pill)
        rows = alpha[max(0, -(top + d)):h - (top + d)]
        layer[max(0, top + d):max(0, top + d) + rows.shape[0], tx + d:tx + d + alpha.shape[1]] = rows
        pill = pill * (1 - layer) + tone * layer
    img[v:v + h, u:u + w] = np.round(pill)
    sheet.put(8, Image.fromarray(img.astype(np.uint8)))


# Pantalla de controles (yosikawa/ctrl01.xtx, índices de 4 bits; grupo 9 de la tabla, desde
# 0x2CBB00): el juego dibuja la textura en tres franjas de 512 x 288 una encima de la otra (los
# nombres de los botones en sus recuadros, lo que hace cada uno y los recuadros con las líneas),
# así que cada rótulo nuevo va en el lugar del original: centrado en él y sobre su misma línea base.
# Letra blanca suavizada parecida a Bahnschrift SemiBold SemiCondensed (mide lo mismo en inglés).
CTRL01 = "yosikawa/ctrl01.xtx"
CTRL_FONT = ("C:/Windows/Fonts/bahnschrift.ttf", 14, b"SemiBold SemiCondensed")
CTRL_LINE = 16  # entre las líneas de un rótulo de dos
CTRL_LABELS = [  # zona del rótulo original en la vista de 4 bits (x0, y0, x1, y1): texto nuevo
    ((30, 20, 135, 42), "Botones L2/R2"), ((30, 60, 135, 84), "Botones L1/R1"),
    ((20, 100, 150, 128), "Botones de dirección"), ((30, 155, 135, 175), "Botón SELECT"),
    ((25, 200, 145, 222), "Joystick izquierdo"), ((205, 220, 305, 240), "Botón START"),
    ((365, 200, 487, 222), "Joystick derecho"),
    ((420, 20, 470, 42), "Botón"), ((420, 60, 470, 84), "Botón"),  # después del ícono △ ○ × □
    ((420, 100, 470, 128), "Botón"), ((420, 140, 470, 160), "Botón"),
    ((10, 328, 155, 349), "Cambiar categoría"), ((25, 368, 135, 392), "Cambiar personaje"),
    ((45, 410, 130, 436), "Mover cursor"), ((50, 463, 112, 486), "Sin uso"),
    ((40, 509, 125, 530), "Mover cursor"), ((375, 328, 495, 349), "Abrir/cerrar menú"),
    ((405, 368, 465, 392), "Confirmar"), ((390, 410, 480, 436), "Cancelar/Volver"),
    ((355, 450, 497, 486), "Quitar habilidades\n(en el menú Estado)"),
    ((365, 509, 490, 550), "Girar el navegador\nde habilidades"),
    ((190, 525, 320, 565), "Cambiar de líder\n(en el menú Grupo)"),
]


def ctrl01(sheet, read):
    img = np.array(sheet.view(4), float) / 255
    path, size, variation = CTRL_FONT
    for (x0, y0, x1, y1), text in CTRL_LABELS:
        zone = img[y0:y1, x0:x1]
        ink = zone > 0.15
        xs = np.nonzero(ink.any(axis=0))[0]
        a, b = _runs(ink.any(axis=1))[0]  # la primera línea
        x = np.nonzero(ink[a:b].any(axis=0))[0][0]
        first = ink[a:b, x:x + 3]  # su primera letra no baja de la línea base
        base, center = y0 + a + np.nonzero(first.any(axis=1))[0][-1] + 1, x0 + (xs[0] + xs[-1] + 1) / 2
        zone[:] = 0
        for k, line in enumerate(text.split("\n")):
            alpha, baseline = text_mask(line, path, size, variation=variation)
            y, x = base + k * CTRL_LINE - round(baseline), round(center - alpha.shape[1] / 2)
            assert x >= 0 and x + alpha.shape[1] <= img.shape[1], f"{line!r} no entra"
            img[y:y + alpha.shape[0], x:x + alpha.shape[1]] = np.maximum(img[y:y + alpha.shape[0], x:x + alpha.shape[1]], alpha)
    sheet.put(4, Image.fromarray(np.round(img * 255).astype(np.uint8)))


# Carteles de la pantalla del grupo, en otra fuente (letras en bloque de 7 filas, casi de ancho
# fijo): en COMBATANT la letra es oscura sobre una franja clara y en RESERVE, clara sobre oscura.
BANNERS = {  # texto original: (recorte, columnas del texto, ¿letra oscura?)
    "COMBATANT": ((374, 113, 100, 18), (11, 91), True),
    "RESERVE": ((374, 131, 100, 18), (18, 81), False),
}
BANNER_TEXT = {"COMBATANT": "COMBATE", "RESERVE": "RESERVA"}  # "EN COMBATE" no entra
BANNER_ROWS = (5, 12)  # filas de las letras dentro del recorte


def _banner_mask(rows, dark):
    return rows < 0x60 if dark else rows >= 0x98


def banners(img):
    glyphs, gaps = {}, {}  # letra -> (máscara, índices, cartel de donde sale)
    r0, r1 = BANNER_ROWS
    for word, ((u, v, w, h), (a, b), dark) in BANNERS.items():
        rows = img[v + r0:v + r1, u:u + w]
        mask = _banner_mask(rows, dark)
        runs = []
        for x0, x1 in _runs(mask[:, a:b].any(axis=0)):
            if x1 - x0 > 12:  # dos letras pegadas (la A y la N de COMBATANT)
                runs += [(x0, (x0 + x1) // 2), ((x0 + x1) // 2, x1)]
            else:
                runs.append((x0, x1))
        assert len(runs) == len(word), f"cartel {word}: {len(runs)} letras"
        for (x0, x1), ch in zip(runs, word):
            glyphs[ch] = glyphs.get(ch) or (mask[:, a + x0:a + x1], rows[:, a + x0:a + x1].copy(), word)
        gaps[word] = round(np.mean([c - b_ for (_, b_), (c, _) in zip(runs, runs[1:])]))
    for word, text in BANNER_TEXT.items():
        (u, v, w, h), (a, b), dark = BANNERS[word]
        rng = np.random.default_rng(zlib.crc32(text.encode()))
        band = img[v + r0:v + r1, u:u + w]
        mask = _banner_mask(band, dark)
        tone = np.bincount(band[:, a:b][mask[:, a:b]]).argmax()
        # la franja sin el texto: cada fila toma muestras de lo que no es letra (ni su borde)
        hole = _near(mask, 1.5)
        rest = band[:, a:b][~hole[:, a:b]]
        for y in range(band.shape[0]):
            free = band[y, a:b][~hole[y, a:b]]
            band[y, a:b][hole[y, a:b]] = rng.choice(free if len(free) else rest, hole[y, a:b].sum())
        total = sum(glyphs[ch][0].shape[1] for ch in text) + gaps[word] * (len(text) - 1)
        x = round((a + b - total) / 2)
        for ch in text:
            m, values, src = glyphs[ch]
            block = band[:, x:x + m.shape[1]]
            block[m] = values[m] if src == word else tone  # la que viene del otro cartel, con el tono de este
            x += m.shape[1] + gaps[word]


EDITS = {  # (volumen, ruta): (función(Sheet, read) que modifica la textura, vistas que cambia);
    # read(ruta) da otro archivo original del mismo volumen
    (0, STAT): (stat, (8,)),
    (0, FONT): (font_xtx, (8, 4)),
    (0, BG01): (bg01, (8,)),
    (0, OBJ01): (obj01, (8,)),
    (0, G2_01): (g2_01, (8,)),
    (0, SEG01): (seg01, (8,)),
    (0, G2_02): (g2_02, (8,)),
    (0, CTRL01): (ctrl01, (4,)),
}


def patch_exe(data):
    """Aplica EXE_PATCHES (u16) y el bucle de save_load_code() al ejecutable, después de comprobar
    los valores originales."""
    data = bytearray(data)
    for pos, (old, new) in EXE_PATCHES.items():
        assert struct.unpack_from("<H", data, pos)[0] == old, f"ejecutable: {pos:#x} no tiene {old}"
        struct.pack_into("<H", data, pos, new)
    pos, original, code = save_load_code()
    assert data[pos:pos + len(original)] == original, "ejecutable: el cartel LOAD/SAVE no es el esperado"
    data[pos:pos + len(code)] = code
    return bytes(data)


# Pantalla de "The Story So Far" (yajima/synopsis.bin: dos .xtx de 512 x 128 en color de 32 bits,
# alfa 0-128). "Loading..." en Courier New Bold con sombra suave y "○ button: Start" sobre una
# barra: se borra el texto y se escribe con una fuente del sistema parecida.
SYNOPSIS = "yajima/synopsis.bin"
SYNOPSIS_TEXTS = [  # (inicio del .xtx, texto, fuente, tamaño, línea base, x, alineado, color, sombra)
    (0x40, "Cargando...", "C:/Windows/Fonts/courbd.ttf", 21, 24, 436, "derecha", (166, 179, 209),
     ((60, 60, 66), 0.35, 1.0)),
    (0x400C0, "Empezar", "C:/Windows/Fonts/segoeui.ttf", 20, 25, 351, "izquierda", (182, 194, 222),
     ((20, 11, 14), 0.8, 0.6)),
]
SYNOPSIS_CLEAR = {0x40: (300, 8, 442, 34), 0x400C0: (349, 9, 468, 31)}  # lo que ocupa el inglés


def text_mask(text, path, size, scale=4, variation=None):
    """Máscara suavizada (0-1) del texto y la fila de su línea base (variation: una de las
    instancias de una fuente variable, como b"Bold Condensed")."""
    from PIL import ImageDraw, ImageFont
    font = ImageFont.truetype(path, size * scale)
    if variation:
        font.set_variation_by_name(variation)
    width = font.getbbox(text)[2] + 2 * scale
    big = Image.new("L", (width + scale - width % scale, size * 2 * scale), 0)
    ImageDraw.Draw(big).text((scale, 0), text, font=font, fill=255)
    small = np.array(big.resize((big.width // scale, big.height // scale), Image.BOX), float) / 255
    cols = np.nonzero(small.any(axis=0))[0]
    return small[:, cols[0]:cols[-1] + 1], font.getbbox("E")[3] / scale


def _over(dst, rgb, alpha):
    """Pinta (rgb, alfa 0-1) sobre una imagen RGBA del GS (alfa 0-128)."""
    a_dst = dst[..., 3:4] / 128
    a = alpha[..., None]
    out_a = a + a_dst * (1 - a)
    color = (np.array(rgb, float) * a + dst[..., :3] * a_dst * (1 - a)) / np.maximum(out_a, 1e-6)
    dst[..., :3] = np.round(color)
    dst[..., 3:4] = np.round(out_a * 128)


def synopsis_bin(data, read):
    data = bytearray(data)
    for start, text, path, size, baseline, x, align, color, (shadow, strength, blur) in SYNOPSIS_TEXTS:
        xtx = Xtx(data[start:start + struct.unpack_from("<I", data, start + 4)[0]])
        w, _, rows, _, pos, size_ = xtx.images[0]
        px = np.frombuffer(bytes(xtx.data[pos:pos + size_]), np.uint8).reshape(rows, w, 4).astype(float)
        x0, y0, x1, y1 = SYNOPSIS_CLEAR[start]
        if px[y0:y1, x1 + 2, 3].max() > 0:  # sobre la barra: cada fila, como la columna de al lado
            px[y0:y1, x0:x1] = px[y0:y1, x1 + 2:x1 + 3]
        else:
            px[y0:y1, x0:x1] = 0
        mask, base = text_mask(text, path, size)
        if align == "derecha":
            x -= mask.shape[1]
        y = baseline - round(base)
        canvas = np.zeros((rows, w), float)
        canvas[y:y + mask.shape[0], x:x + mask.shape[1]] = mask[:rows - y]
        soft = np.array(Image.fromarray(np.uint8(canvas * 255)).filter(ImageFilter.GaussianBlur(blur)), float) / 255
        shifted = np.zeros_like(soft)
        shifted[2:, 2:] = soft[:-2, :-2] * strength
        _over(px, shadow, shifted)
        _over(px, color, canvas)
        xtx.data[pos:pos + size_] = np.clip(px, 0, 255).astype(np.uint8).tobytes()
        data[start:start + len(xtx.data)] = xtx.data
    return bytes(data)


# Los resúmenes de "The Story So Far" (yajima/synopsis/NN.jpg, 512 x 448): el texto está dibujado
# en la imagen. Se borra (píxeles claros y poco saturados de la zona del texto, con su sombra,
# rellenados desde los vecinos) y se escribe la traducción de traduccion/imagenes/sinopsis.po.
SYNOPSIS_PO = os.path.join(ROOT, "traduccion", "imagenes", "sinopsis.po")
SYN_BODY = {"zona": (20, 128, 500, 440), "x": 37, "base": 148, "paso": 22, "derecha": 478,
            "fuente": "C:/Windows/Fonts/segoeui.ttf", "tamaño": 18, "color": (228, 218, 216)}
SYN_TITLE = {"zona": (24, 72, 200, 95), "x": 25, "base": 89, "ancho_ingles": 146,
             "fuente": "C:/Windows/Fonts/GOTHIC.TTF", "color": (235, 230, 232)}
SYN_SHADOW = ((15, 10, 15), 0.75, 1.0)  # color, intensidad y desenfoque de la sombra (2 px abajo a la derecha)


def _blur(a, r):
    """Desenfoque de caja (dos pasadas) de un arreglo 2D, radio r."""
    for axis in (0, 1):
        for _ in range(2):
            c = np.cumsum(np.pad(a, [(r + 1, r) if k == axis else (0, 0) for k in range(2)], mode="edge"), axis=axis)
            a = (np.take(c, range(2 * r + 1, c.shape[axis]), axis=axis) - np.take(c, range(0, c.shape[axis] - 2 * r - 1), axis=axis)) / (2 * r + 1)
    return a


def inpaint(img, mask):
    """Rellena los píxeles de `mask` con el promedio de los conocidos cercanos, de lo más chico a
    lo más grande (desenfoques normalizados)."""
    out, known = img.copy(), ~mask
    for r in (1, 2, 4, 8, 16, 32):
        w = _blur(known.astype(float), r)
        sel = ~known & (w > 0.05)
        for c in range(3):
            acc = _blur(out[..., c] * known, r)
            out[..., c][sel] = acc[sel] / w[sel]
        known = known | sel
    return out


def _text_pixels(img, zone):
    x0, y0, x1, y1 = zone
    lum, sat = img.mean(axis=2), img.max(axis=2) - img.min(axis=2)
    text = np.zeros(lum.shape, bool)
    text[y0:y1, x0:x1] = ((lum > 150) & (sat < 70))[y0:y1, x0:x1]
    near = _near(text, 2.5)
    shadow = np.zeros_like(near)
    shadow[3:, 3:] = near[:-3, :-3]  # la sombra va abajo a la derecha
    return near | shadow


def _draw(img, text, path, size, x, baseline, color):
    mask, base = text_mask(text, path, size)
    y = baseline - round(base)
    layer = np.zeros(img.shape[:2])
    h, w = min(mask.shape[0], img.shape[0] - y), min(mask.shape[1], img.shape[1] - x)
    layer[y:y + h, x:x + w] = mask[:h, :w]
    tone, strength, blur = SYN_SHADOW
    soft = np.array(Image.fromarray(np.uint8(layer * 255)).filter(ImageFilter.GaussianBlur(blur)), float) / 255
    shadow = np.zeros_like(soft)
    shadow[2:, 2:] = soft[:-2, :-2] * strength
    for alpha, rgb in ((shadow, tone), (layer, color)):
        img[:] = img * (1 - alpha[..., None]) + np.array(rgb, float) * alpha[..., None]


def _title_size(path, cap_width):
    from PIL import ImageFont
    size = 10
    while ImageFont.truetype(path, size + 1).getbbox("The Story So Far:")[2] <= cap_width:
        size += 1
    return size


def synopsis_jpg(data, read, number):
    import po
    texts = {e.msgctxt: e.msgstr for e in po.read(SYNOPSIS_PO)[1] if e.msgstr}
    if number not in texts:
        return data
    from PIL import ImageFont
    original = Image.open(io.BytesIO(data))
    img = np.array(original.convert("RGB"), float)
    mask = _text_pixels(img, SYN_BODY["zona"]) | _text_pixels(img, SYN_TITLE["zona"])
    img = inpaint(img, mask)
    t = SYN_TITLE
    _draw(img, texts.get("titulo", "The Story So Far:"), t["fuente"], _title_size(t["fuente"], t["ancho_ingles"]),
          t["x"], t["base"], t["color"])
    b = SYN_BODY
    font = ImageFont.truetype(b["fuente"], b["tamaño"])
    lines = wrap(texts[number], b["derecha"] - b["x"], lambda s: font.getlength(s))
    for k, line in enumerate(lines.split("\n")):
        _draw(img, line, b["fuente"], b["tamaño"], b["x"], b["base"] + k * b["paso"], b["color"])
    out = io.BytesIO()
    Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8)).save(
        out, "JPEG", qtables=original.quantization, subsampling=2)
    return out.getvalue()


# Paneles 3D de la pantalla del grupo (yosikawa/model/atk.txy y rsv.txy): "<< COMBATANT >>" y
# "<< RESERVE >>" en letras de bloque claras sobre una franja. Entre los dos están todas las
# letras de COMBATE y RESERVA (como en los carteles de obj01).
MODEL_LABELS = {  # archivo: (texto original, columnas del texto, texto nuevo)
    "yosikawa/model/atk.txy": ("COMBATANT", (20, 108), "COMBATE"),
    "yosikawa/model/rsv.txy": ("RESERVE", (30, 98), "RESERVA"),
}
MODEL_ROWS = (9, 22)  # filas de la franja de las letras
MODEL_INK = 0xA0  # desde acá es letra (la franja ronda 0x96)


def _model_glyphs(pixels, word, cols):
    """{letra: (máscara, índices)} y separación de las letras de un panel."""
    r0, r1 = MODEL_ROWS
    band = pixels[r0:r1]
    lo, hi = cols
    runs = [(a + lo, b + lo) for a, b in _runs((band[:, lo:hi] >= 0xD0).sum(axis=0) >= 2)]
    merged = []
    for a, b in runs:  # la V queda en dos tramos finos: se juntan
        if merged and (b - a < 5 or merged[-1][1] - merged[-1][0] < 5) and b - merged[-1][0] <= 10:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    assert len(merged) == len(word), f"panel {word}: {len(merged)} letras"
    glyphs = {}
    for (a, b), ch in zip(merged, word):
        block = band[:, a - 1:b + 1]
        glyphs.setdefault(ch, (block >= MODEL_INK, block.copy()))
    gap = round(np.mean([c - b for (_, b), (c, _) in zip(merged, merged[1:])]))
    return glyphs, gap


def model_panel(path, read):
    pixels = {p: np.frombuffer(Txy(read(p)).pixels(), np.uint8).reshape(64, 256).astype(int) for p in MODEL_LABELS}
    font = {}
    for p, (word, cols, _) in MODEL_LABELS.items():
        glyphs, _ = _model_glyphs(pixels[p], word, cols)
        for ch, g in glyphs.items():
            font.setdefault(ch, g)
    word, (lo, hi), text = MODEL_LABELS[path]
    img = pixels[path]
    _, gap = _model_glyphs(img, word, (lo, hi))
    r0, r1 = MODEL_ROWS
    band = img[r0:r1]
    # la franja sin el texto: el gris de fondo (el valor más común entre 0x80 y la letra)
    gray = band[:, lo:hi][(band[:, lo:hi] >= 0x80) & (band[:, lo:hi] < MODEL_INK)]
    hole = _near(band >= MODEL_INK, 2.5)
    hole[:, :lo] = hole[:, hi:] = False
    band[hole] = np.bincount(gray).argmax()
    total = sum(font[ch][0].shape[1] for ch in text) + (gap - 2) * (len(text) - 1)
    x = round((lo + hi - total) / 2)
    for ch in text:
        mask, values = font[ch]
        block = band[:, x:x + mask.shape[1]]
        block[mask] = values[mask]
        x += mask.shape[1] + gap - 2  # cada letra trae una columna de borde a cada lado
    return Txy(read(path)).store(img.astype(np.uint8).tobytes())


def _synopsis_view(data):
    """Las dos imágenes de synopsis.bin, una debajo de la otra, sobre gris."""
    out = Image.new("RGB", (512, 256), (90, 90, 90))
    for k, start in enumerate((0x40, 0x400C0)):
        xtx = Xtx(data[start:start + struct.unpack_from("<I", data, start + 4)[0]])
        w, _, rows, _, pos, size = xtx.images[0]
        rgba = Image.frombytes("RGBA", (w, rows), bytes(xtx.data[pos:pos + size]))
        alpha = rgba.getchannel("A").point(lambda p: min(255, p * 2))
        out.paste(rgba.convert("RGB"), (0, k * 128), alpha)
    return out


# Menú de la pantalla de título (yajima/titleobj.xtx, comprimido con ARX): una imagen de 32 bits
# de 120 x 108 con una opción cada 18 filas. El brillo de cada píldora está solo en el alfa; el
# color es blanco y la letra, negra suavizada. Se reescribe el color con una letra parecida
# (Arial, un poco angosta como la original; las largas, más angostas para que entren en la píldora).
TITLE_MENU = "yajima/titleobj.xtx"
TITLE_OPTIONS = ["NUEVA PARTIDA", "CONTINUAR", "INSTALAR", "DESINSTALAR", "SALIR", "TEATRO"]
TITLE_FONT, TITLE_SIZE, TITLE_SQUEEZE, TITLE_WIDTH = "C:/Windows/Fonts/arial.ttf", 17, 0.92, 92


def _title_rgba(data):
    xtx = Xtx(data)
    w, _, rows, _, start, size = xtx.images[0]
    return xtx, start, np.frombuffer(bytes(xtx.data[start:start + size]), np.uint8).reshape(rows, w, 4).copy()


def title_menu(data, read):
    import arx
    xtx, start, px = _title_rgba(arx.decompress(data))
    rows, w = px.shape[:2]
    for i, text in enumerate(TITLE_OPTIONS):
        alpha, base = text_mask(text, TITLE_FONT, TITLE_SIZE)
        width = min(TITLE_WIDTH, round(alpha.shape[1] * TITLE_SQUEEZE))
        alpha = np.array(Image.fromarray(np.round(alpha * 255).astype(np.uint8)).resize((width, alpha.shape[0]), Image.LANCZOS), float) / 255
        band = px[18 * i:18 * i + 18]
        band[..., :3] = 255
        y, x = 16 - round(base), (w - width) // 2
        rows_ = alpha[max(0, -y):18 - y]
        lum = np.round(255 * (1 - rows_)).astype(np.uint8)
        region = band[max(0, y):max(0, y) + rows_.shape[0], x:x + width, :3]
        region[:] = np.minimum(region, lum[..., None])
    xtx.data[start:start + px.size] = px.tobytes()
    return arx.compress(bytes(xtx.data))


def _title_view(data):
    import arx
    _, _, px = _title_rgba(arx.decompress(data))
    im = Image.fromarray(px, "RGBA")
    out = Image.new("RGB", im.size, (40, 40, 90))
    out.paste(im.convert("RGB"), (0, 0), im.getchannel("A"))
    return out


# Logo de la pantalla de título (yajima/title.bin y title2.bin, ARX): imagen de 32 bits de
# 512 x 448 (alfa 0-128) con "DISC 1" o "DISC 2" en gris oscuro sobre un halo blanco opaco, bajo
# la ®. Queda "DISCO n", empezando en el mismo lugar; el halo se extiende para la letra de más.
TITLE_LOGOS = {"yajima/title.bin": "DISCO 1", "yajima/title2.bin": "DISCO 2"}
DISC_TEXT = (412, 160, 7, 0x10)  # x, fila de arriba de la mayúscula, alto, gris de la letra
DISC_CLEAR = (410, 159, 442, 168)  # lo que ocupa el texto original (x0, y0, x1, y1)


def title_logo(path, data):
    import arx
    px = np.frombuffer(arx.decompress(data), np.uint8).reshape(448, 512, 4).copy()
    x0, y0, x1, y1 = DISC_CLEAR
    px[y0:y1, x0:x1, :3] = 255
    x, top, cap, gray = DISC_TEXT
    alpha, base = text_mask(TITLE_LOGOS[path], "C:/Windows/Fonts/arial.ttf", 10)
    y = top + cap - round(base)
    h, w = alpha.shape
    region = px[y:y + h, x:x + w]
    lum = np.round(255 - alpha * (255 - gray)).astype(np.uint8)
    region[..., :3] = np.minimum(region[..., :3], lum[..., None])
    ink = _near(alpha > 0.1, 2)
    region[..., 3][ink] = np.maximum(region[..., 3][ink], 126)
    return arx.compress(px.tobytes())


def _logo_view(data):
    import arx
    im = Image.frombytes("RGBA", (512, 448), arx.decompress(data))
    out = Image.new("RGB", im.size, (255, 255, 255))
    out.paste(im.convert("RGB"), (0, 0), im.getchannel("A").point(lambda p: min(255, 2 * p)))
    return out.crop((360, 120, 480, 190)).resize((360, 210), Image.NEAREST)


# Pantallas en JPG de yajima: "GAME OVER" y "TO BE CONTINUED" (letras suavizadas con un brillo
# cian sobre negro) y el ajuste de la pantalla (mnt_set: "- CENTER -" y la leyenda de los botones,
# gris claro sobre gris oscuro liso). Se borra la zona del texto (con el color del fondo, que es
# liso) y se escribe el nuevo con una letra parecida, cada letra en su lugar cuando el original va
# espaciado. Se guardan con las tablas de cuantización originales, como las sinopsis.
JPG_SCREENS = {  # archivo: [(zona a borrar o None, color del fondo, texto, fuente, tamaño, colocación, línea base, color, brillo)]
    # colocación: ("paso", centro, distancia entre caracteres), ("letras", [centro de cada letra]),
    # ("izq", x) o ("caja", x0, x1): estirada para ocupar de x0 a x1
    "yajima/gameov1.jpg": [((40, 196, 480, 238), (0, 0, 0), "FIN DEL JUEGO", "arial.ttf", 19, ("paso", 257, 30), 222,
                            (140, 178, 170), (4, (70, 120, 112)))],
    "yajima/end.jpg": [((120, 196, 400, 238), (0, 0, 0), "CONTINUARÁ", "courbd.ttf", 24, ("paso", 257, 14.4), 222,
                        (150, 182, 176), (4, (70, 120, 112)))],
    "yajima/mnt_set.jpg": [
        ((187, 219, 324, 231), (49, 50, 55), "–", "GOTHICB.TTF", 10, ("caja", 202, 212), 228, (172, 171, 187), None),
        (None, None, "–", "GOTHICB.TTF", 10, ("caja", 297, 308), 228, (172, 171, 187), None),
        (None, None, "CENTRO", "GOTHICB.TTF", 10, ("caja", 219, 291), 228, (172, 171, 187), None),  # letra extendida
        ((410, 350, 492, 370), (49, 50, 55), ": aceptar", "verdana.ttf", 15, ("izq", 413), 364, (172, 171, 187), None),
        ((410, 376, 492, 396), (49, 50, 55), ": cancelar", "verdana.ttf", 15, ("izq", 413), 390, (172, 171, 187), None),
        ((410, 402, 492, 422), (49, 50, 55), ": inicial", "verdana.ttf", 15, ("izq", 413), 416, (172, 171, 187), None),
    ],
}


def jpg_screen(path, data):
    original = Image.open(io.BytesIO(data))
    img = np.array(original.convert("RGB"), float)
    for zone, background, text, font, size, place, baseline, color, glow in JPG_SCREENS[path]:
        if zone:
            x0, y0, x1, y1 = zone
            img[y0:y1, x0:x1] = background
        layer = np.zeros(img.shape[:2])
        kind = place[0]
        if kind in ("izq", "caja"):
            chars = [(text, place[1])]
        else:
            glyphs = [c for c in text if c != " "]
            if kind == "paso":  # cada carácter (también los espacios) a la misma distancia, centrado
                _, center, step = place
                starts = [center + (k - (len(text) - 1) / 2) * step for k in range(len(text))]
                chars = [(c, x) for c, x in zip(text, starts) if c != " "]
            else:  # una letra (sin espacios) en el centro de cada letra original
                chars = list(zip(glyphs, place[1]))
        for chunk, x in chars:
            mask, base = text_mask(chunk, "C:/Windows/Fonts/" + font, size)
            if kind == "caja":  # estirada a lo ancho hasta ocupar lo mismo que la original
                width = place[2] - place[1]
                mask = np.array(Image.fromarray(np.uint8(mask * 255)).resize((width, mask.shape[0]), Image.LANCZOS), float) / 255
            left = round(x) if kind in ("izq", "caja") else round(x - mask.shape[1] / 2)
            y = baseline - round(base)
            h, w = mask.shape
            layer[y:y + h, left:left + w] = np.maximum(layer[y:y + h, left:left + w], mask)
        if glow:
            sigma, tone = glow
            soft = np.array(Image.fromarray(np.uint8(layer * 255)).filter(ImageFilter.GaussianBlur(1)), float) / 255
            halo = np.array(Image.fromarray(np.uint8(layer * 255)).filter(ImageFilter.GaussianBlur(sigma)), float) / 255
            img += halo[..., None] * np.array(tone, float) + soft[..., None] * np.array(color, float)
        else:
            img = img * (1 - layer[..., None]) + np.array(color, float) * layer[..., None]
    out = io.BytesIO()
    Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8)).save(out, "JPEG", qtables=original.quantization, subsampling=2)
    return out.getvalue()


# Fuentes del texto (font0.us, font1.us): cabecera de 0x40 bytes y dos texturas que se suben como
# PSMCT32 de 320 x 192 y se leen como PSMT4 de 640 x 768; cada nibble guarda dos capas de 2 bits,
# con glifos de 20 x 24 en filas de 32 (1024 por capa). El espacio duro (0xA0, glifo 256) tiene
# dibujado un adorno que en los textos de la Ruta SG se ve como un punto delante de ¡ y ¿ (ver
# x2text.GsText): se borra para que sea un espacio de 6 píxeles.
FONTS = ("font0.us", "font1.us")
FONT_TEXTURE = 245760
BLANK_GLYPHS = (256,)


def _font_texture(data, layer):
    from gs import Gs
    start = 0x40 + layer // 2 * FONT_TEXTURE
    gs = Gs()
    gs.write32(0, 5, 320, 192, data[start:start + FONT_TEXTURE])
    return gs, start, bytearray(gs.read4(0, 10, 640, 768))


def blank_glyphs(data, read):
    data = bytearray(data)
    for glyph in BLANK_GLYPHS:
        layer, within = divmod(glyph, 1024)
        row, col = divmod(within, 32)
        gs, start, px = _font_texture(data, layer)
        keep = ~(3 << 2 * (layer % 2)) & 0xF
        for y in range(24 * row, 24 * row + 24):
            px[640 * y + 20 * col:640 * y + 20 * col + 20] = bytes(p & keep for p in px[640 * y + 20 * col:640 * y + 20 * col + 20])
        gs.write4(0, 10, 640, 768, px)
        data[start:start + FONT_TEXTURE] = gs.read32(0, 5, 320, 192)
    return bytes(data)


def _font_view(data):
    """Los glifos 224-287 (0x80-0xBF) de la capa 0."""
    _, _, px = _font_texture(data, 0)
    rows = np.frombuffer(bytes(px), np.uint8).reshape(768, 640)[168:216] & 3
    return Image.fromarray((rows * 85).astype(np.uint8))


BYTE_EDITS = {  # archivo: (función(bytes, read) -> bytes nuevos, vista previa(bytes) -> imagen)
    **{path: (blank_glyphs, _font_view) for path in FONTS},
    TITLE_MENU: (title_menu, _title_view),
    **{path: (lambda data, read, path=path: jpg_screen(path, data), lambda data: Image.open(io.BytesIO(data)).convert("RGB"))
       for path in JPG_SCREENS},
    **{path: (lambda data, read, path=path: title_logo(path, data), _logo_view) for path in TITLE_LOGOS},
    **{path: (lambda data, read, path=path: model_panel(path, read),
              lambda data: Image.frombytes("L", (256, 64), Txy(data).pixels())) for path in MODEL_LABELS},
    SYNOPSIS: (synopsis_bin, _synopsis_view),
    **{f"yajima/synopsis/{n:02d}.jpg": (lambda data, read, n=n: synopsis_jpg(data, read, f"{n:02d}"),
                                         lambda data: Image.open(io.BytesIO(data)).convert("RGB")) for n in range(1, 23)},
}


def replacements(read):
    """{(volumen, ruta): bytes nuevos}; read(volumen, ruta) da el archivo original."""
    out = {}
    for key, (fn, _) in EDITS.items():
        sheet = Sheet(read(*key))
        fn(sheet, lambda path: read(key[0], path))
        out[key] = sheet.to_bytes()
    for path, (fn, _) in BYTE_EDITS.items():
        out[(0, path)] = fn(read(0, path), lambda p: read(0, p))
    return out


def preview():
    from x2iso import Iso, Volume, iso_paths
    vol = Volume(Iso(iso_paths()[0]), 0)
    read = lambda p: vol.read(vol.by_path[p])
    pairs = []
    for (group, path), (fn, views) in EDITS.items():
        sheet = Sheet(read(path))
        before = [sheet.view(psm) for psm in views]
        fn(sheet, read)
        pairs += [(path, psm, old, sheet.view(psm)) for psm, old in zip(views, before)]
    for path, (fn, view) in BYTE_EDITS.items():
        old, new = view(read(path)), view(fn(read(path), read))
        pairs.append((path, 8, old, new))
    for path, psm, old, new in pairs:
        out = Image.new(old.mode, (old.width, old.height * 2))
        out.paste(old, (0, 0))
        out.paste(new, (0, old.height))
        name = path.replace("/", "__").rsplit(".", 1)[0]
        out.save(os.path.join(ROOT, "work", "tex", f"es_{name}_t{psm}.png"))
        print(name, psm)


if __name__ == "__main__":
    if sys.argv[1:] == ["ver"]:
        preview()
    else:
        print(__doc__)
