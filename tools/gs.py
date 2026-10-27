"""Memoria de video (GS) de la PS2, para ver y modificar texturas.

El juego sube las imágenes como PSMCT32 (32 bits por píxel) a una dirección de
la memoria de video y después las lee en otro formato: PSMT8 o PSMT4 (índices
de 8 o 4 bits) con una paleta (CLUT) que también está en la memoria. Cada
formato reparte los píxeles en páginas de 8 KB y bloques de 256 bytes de otra
manera, así que para ver una textura hay que escribirla como la sube el juego
y leerla como la usa; para modificarla, el camino inverso.

Direcciones: bp (base) en bloques de 256 bytes, bw (ancho del búfer) en
unidades de 64 píxeles, como en los registros del GS. Tablas del diseño de
memoria del GS (las mismas que tools/gs_swizzle.py del Episode I).
"""

BLOCK32 = [
    [0, 1, 4, 5, 16, 17, 20, 21],
    [2, 3, 6, 7, 18, 19, 22, 23],
    [8, 9, 12, 13, 24, 25, 28, 29],
    [10, 11, 14, 15, 26, 27, 30, 31],
]
COLUMN32 = [
    [0, 1, 4, 5, 8, 9, 12, 13],
    [2, 3, 6, 7, 10, 11, 14, 15],
    [16, 17, 20, 21, 24, 25, 28, 29],
    [18, 19, 22, 23, 26, 27, 30, 31],
    [32, 33, 36, 37, 40, 41, 44, 45],
    [34, 35, 38, 39, 42, 43, 46, 47],
    [48, 49, 52, 53, 56, 57, 60, 61],
    [50, 51, 54, 55, 58, 59, 62, 63],
]
BLOCK4 = [
    [0, 2, 8, 10],
    [1, 3, 9, 11],
    [4, 6, 12, 14],
    [5, 7, 13, 15],
    [16, 18, 24, 26],
    [17, 19, 25, 27],
    [20, 22, 28, 30],
    [21, 23, 29, 31],
]
_C4 = [
    [0, 8, 32, 40, 64, 72, 96, 104, 2, 10, 34, 42, 66, 74, 98, 106,
     4, 12, 36, 44, 68, 76, 100, 108, 6, 14, 38, 46, 70, 78, 102, 110],
    [16, 24, 48, 56, 80, 88, 112, 120, 18, 26, 50, 58, 82, 90, 114, 122,
     20, 28, 52, 60, 84, 92, 116, 124, 22, 30, 54, 62, 86, 94, 118, 126],
    [65, 73, 97, 105, 1, 9, 33, 41, 67, 75, 99, 107, 3, 11, 35, 43,
     69, 77, 101, 109, 5, 13, 37, 45, 71, 79, 103, 111, 7, 15, 39, 47],
    [81, 89, 113, 121, 17, 25, 49, 57, 83, 91, 115, 123, 19, 27, 51, 59,
     85, 93, 117, 125, 21, 29, 53, 61, 87, 95, 119, 127, 23, 31, 55, 63],
    [192, 200, 224, 232, 128, 136, 160, 168, 194, 202, 226, 234, 130, 138, 162, 170,
     196, 204, 228, 236, 132, 140, 164, 172, 198, 206, 230, 238, 134, 142, 166, 174],
    [208, 216, 240, 248, 144, 152, 176, 184, 210, 218, 242, 250, 146, 154, 178, 186,
     212, 220, 244, 252, 148, 156, 180, 188, 214, 222, 246, 254, 150, 158, 182, 190],
    [129, 137, 161, 169, 193, 201, 225, 233, 131, 139, 163, 171, 195, 203, 227, 235,
     133, 141, 165, 173, 197, 205, 229, 237, 135, 143, 167, 175, 199, 207, 231, 239],
    [145, 153, 177, 185, 209, 217, 241, 249, 147, 155, 179, 187, 211, 219, 243, 251,
     149, 157, 181, 189, 213, 221, 245, 253, 151, 159, 183, 191, 215, 223, 247, 255],
]
COLUMN4 = _C4 + [[v + 256 for v in row] for row in _C4]
_C8 = [
    [0, 4, 16, 20, 32, 36, 48, 52, 2, 6, 18, 22, 34, 38, 50, 54],
    [8, 12, 24, 28, 40, 44, 56, 60, 10, 14, 26, 30, 42, 46, 58, 62],
    [33, 37, 49, 53, 1, 5, 17, 21, 35, 39, 51, 55, 3, 7, 19, 23],
    [41, 45, 57, 61, 9, 13, 25, 29, 43, 47, 59, 63, 11, 15, 27, 31],
    [96, 100, 112, 116, 64, 68, 80, 84, 98, 102, 114, 118, 66, 70, 82, 86],
    [104, 108, 120, 124, 72, 76, 88, 92, 106, 110, 122, 126, 74, 78, 90, 94],
    [65, 69, 81, 85, 97, 101, 113, 117, 67, 71, 83, 87, 99, 103, 115, 119],
    [73, 77, 89, 93, 105, 109, 121, 125, 75, 79, 91, 95, 107, 111, 123, 127],
]
COLUMN8 = _C8 + [[v + 128 for v in row] for row in _C8]


def addr32(bp, bw, x, y):
    """Dirección en bytes del píxel (x, y) de un búfer PSMCT32."""
    page = x // 64 + (y // 32) * bw
    block = BLOCK32[(y // 8) % 4][(x // 8) % 8]
    return bp * 256 + page * 8192 + block * 256 + COLUMN32[y % 8][x % 8] * 4


def addr8(bp, bw, x, y):
    """Dirección en bytes del píxel (x, y) de una textura PSMT8 (bw par)."""
    page = x // 128 + (y // 64) * (bw // 2)
    block = BLOCK32[(y // 16) % 4][(x // 16) % 8]
    return bp * 256 + page * 8192 + block * 256 + COLUMN8[y % 16][x % 16]


def addr4(bp, bw, x, y):
    """Dirección en nibbles del píxel (x, y) de una textura PSMT4 (bw par)."""
    page = x // 128 + (y // 128) * (bw // 2)
    block = BLOCK4[(y // 16) % 8][(x // 32) % 4]
    return bp * 512 + page * 16384 + block * 512 + COLUMN4[y % 16][x % 32]


class Gs:
    def __init__(self):
        self.mem = bytearray(4 << 20)

    def write32(self, bp, bw, w, h, data):
        """Sube un rectángulo w x h de píxeles de 32 bits (como una transferencia del juego)."""
        mem = self.mem
        for y in range(h):
            for x in range(w):
                a, k = addr32(bp, bw, x, y), 4 * (y * w + x)
                mem[a:a + 4] = data[k:k + 4]

    def read32(self, bp, bw, w, h):
        out = bytearray(4 * w * h)
        for y in range(h):
            for x in range(w):
                a, k = addr32(bp, bw, x, y), 4 * (y * w + x)
                out[k:k + 4] = self.mem[a:a + 4]
        return bytes(out)

    def read8(self, bp, bw, w, h):
        mem = self.mem
        return bytes(mem[addr8(bp, bw, x, y)] for y in range(h) for x in range(w))

    def write8(self, bp, bw, w, h, pixels):
        for y in range(h):
            for x in range(w):
                self.mem[addr8(bp, bw, x, y)] = pixels[y * w + x]

    def read4(self, bp, bw, w, h):
        mem, out = self.mem, bytearray(w * h)
        for y in range(h):
            for x in range(w):
                n = addr4(bp, bw, x, y)
                out[y * w + x] = mem[n >> 1] >> 4 if n & 1 else mem[n >> 1] & 0xF
        return bytes(out)

    def write4(self, bp, bw, w, h, pixels):
        mem = self.mem
        for y in range(h):
            for x in range(w):
                n, v = addr4(bp, bw, x, y), pixels[y * w + x] & 0xF
                mem[n >> 1] = (mem[n >> 1] & 0x0F) | (v << 4) if n & 1 else (mem[n >> 1] & 0xF0) | v

    def clut(self, cbp, colors):
        """Paleta RGBA de 16 o 256 colores guardada como PSMCT32 (modo CSM1). En las de
        256 colores el GS intercambia los bloques 8-15 y 16-23 de cada grupo de 32."""
        w = 8 if colors == 16 else 16
        raw = self.read32(cbp, 1, w, colors // w)
        pal = [raw[4 * i:4 * i + 4] for i in range(colors)]
        if colors == 256:
            pal = [pal[(i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)] for i in range(256)]
        return pal
