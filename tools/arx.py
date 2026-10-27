"""Archivos comprimidos "ARX" (yajima/titleobj.xtx, title.bin, title2.bin).

Formato (deducido del descompresor del ejecutable, 0x194A10):
  0x00 "ARX\\0" | u32 tamaño descomprimido | u32 tamaño del archivo | u32 0
  0x10 tabla de 30 palabras de 32 bits (las más frecuentes)
  0x88 un solo flujo de palabras de 32 bits, que se lee en orden: cuando el lector de bits se
       queda sin bits, la palabra siguiente pasa a ser la de bits (se leen del más alto al más
       bajo); las demás son palabras literales.
Cada palabra de la salida es un bit 0 seguido de una palabra literal, o un bit 1 y un índice de
la tabla con un código de Exp-Golomb: k unos y un cero, y después k + 1 bits que se suman a
2 + 4 + ... (0-1, 2-5, 6-13, 14-29).
"""
import struct
from collections import Counter

MAGIC = b"ARX\0"
TABLE = 30


def decompress(data):
    assert data[:4] == MAGIC and struct.unpack_from("<I", data, 12)[0] == 0, "no es un ARX"
    size = struct.unpack_from("<I", data, 4)[0]
    table = struct.unpack_from(f"<{TABLE}I", data, 16)
    pos, buf, left = 0x88, 0, 0
    out = []

    def word():
        nonlocal pos
        w = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return w

    def bit():
        nonlocal buf, left
        if left == 0:
            buf, left = word(), 32
        left -= 1
        b = buf >> 31
        buf = (buf << 1) & 0xFFFFFFFF
        return b

    while 4 * len(out) < size:
        if not bit():
            out.append(word())
            continue
        k, base = 1, 0
        while bit():
            base += 1 << k
            k += 1
        value = 0
        for _ in range(k):
            value = 2 * value + bit()
        out.append(table[base + value])
    return struct.pack(f"<{len(out)}I", *out)[:size]


def compress(data):
    """Lo inverso de decompress (el tamaño tiene que ser múltiplo de 4)."""
    assert len(data) % 4 == 0
    words = struct.unpack(f"<{len(data) // 4}I", data)
    table = [w for w, _ in Counter(words).most_common(TABLE)]
    table += [0] * (TABLE - len(table))
    index = {w: i for i, w in enumerate(table)}
    stream, slot, left = [], None, 0

    def put_bit(b):
        nonlocal slot, left
        if left == 0:
            slot, left = len(stream), 32
            stream.append(0)
        left -= 1
        stream[slot] |= b << left

    for w in words:
        if w not in index:
            put_bit(0)
            stream.append(w)
            continue
        put_bit(1)
        i, k, base = index[w], 1, 0
        while i >= base + (1 << k):
            put_bit(1)
            base += 1 << k
            k += 1
        put_bit(0)
        for j in range(k - 1, -1, -1):
            put_bit(((i - base) >> j) & 1)
    body = struct.pack(f"<{TABLE}I", *table) + struct.pack(f"<{len(stream)}I", *stream)
    return MAGIC + struct.pack("<III", len(data), 16 + len(body), 0) + body
