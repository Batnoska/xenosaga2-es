"""Texturas .xtx (y .txy de los modelos del menú) de Xenosaga Episode II.

Formato:
  0x00 "XTX\\0" | u32 tamaño total | u32 cantidad de imágenes | u32 inicio de la tabla
  tabla: por imagen 20 bytes
    u16 ancho | u16 ancho del búfer de destino (unidades de 64 píxeles, DBW)
    u32 alto | u32 dirección en la memoria de video (en palabras de 4 bytes)
    u32 cantidad de quadwords del paquete | u32 inicio del paquete
  paquete: código VIF DIRECT + GIFtag en modo IMAGE + píxeles PSMCT32.

El juego sube cada imagen como PSMCT32 y la usa como PSMT8 o PSMT4 (índices
de 8 o 4 bits). En la interfaz las paletas son rampas de intensidad y el color
lo pone el juego al dibujar, así que el índice funciona como un nivel de gris:
las imágenes se exportan en escala de grises (8 bits: gris = índice; 4 bits:
gris = índice × 17) y se importan igual.
"""
import struct

from gs import Gs


class Xtx:
    def __init__(self, data):
        assert data[:4] == b"XTX\0", "no es un .xtx"
        self.data = bytearray(data)
        count, table = struct.unpack_from("<2I", data, 8)
        self.images = []  # (ancho, dbw, filas, dirección en palabras, inicio de los píxeles, bytes)
        for i in range(count):
            w, dbw, _, vram, _, off = struct.unpack_from("<HHIIII", data, table + 20 * i)
            nloop = struct.unpack_from("<Q", data, off + 16)[0] & 0x7FFF
            size = nloop * 16
            self.images.append((w, dbw, size // (4 * w), vram, off + 32, size))

    @property
    def dbw(self):
        return self.images[0][1]

    def memory(self):
        """La memoria de video tal como queda después de subir todas las imágenes."""
        gs = Gs()
        for w, dbw, rows, vram, start, size in self.images:
            gs.write32(vram // 64, dbw, w, rows, self.data[start:start + size])
        return gs

    def store(self, gs):
        """Vuelve a guardar en el archivo lo que haya en la memoria de video."""
        for w, dbw, rows, vram, start, size in self.images:
            self.data[start:start + size] = gs.read32(vram // 64, dbw, w, rows)
        return bytes(self.data)

    def extent(self, psm):
        """(ancho, alto) de toda la memoria usada vista como PSMT8 o PSMT4. Cada página de
        PSMCT32 (64 x 32) es una de 128 x 64 en PSMT8 y de 128 x 128 en PSMT4, y una imagen más
        angosta que el búfer ocupa igual filas enteras de páginas."""
        page_rows = max((vram // 2048) // self.dbw + -(-rows // 32) for _, _, rows, vram, _, _ in self.images)
        return 128 * self.dbw, page_rows * (64 if psm == 8 else 128)

    def read(self, gs, psm):
        """Imagen en gris (bytes) de toda la memoria usada, en PSMT8 o PSMT4."""
        w, h = self.extent(psm)
        if psm == 8:
            return w, h, gs.read8(0, 2 * self.dbw, w, h)
        return w, h, bytes(p * 17 for p in gs.read4(0, 2 * self.dbw, w, h))

    def write(self, gs, psm, pixels):
        w, h = self.extent(psm)
        if psm == 8:
            gs.write8(0, 2 * self.dbw, w, h, pixels)
        else:
            gs.write4(0, 2 * self.dbw, w, h, bytes((p + 8) // 17 for p in pixels))


class Txy:
    """Texturas de los modelos del menú (yosikawa/model/*.txy): "txy\\0" y una tabla en 0xB0 de
    20 bytes por imagen (inicio del paquete, dirección, ancho, alto...). Cada imagen es un paquete
    VIF DIRECT + GIFtag IMAGE con píxeles PSMCT32 de ancho x alto, que el juego lee como PSMT8
    del doble de ancho y alto (128 x 32 -> 256 x 64)."""

    def __init__(self, data, index=0):
        assert data[:4] == b"txy\0", "no es un .txy"
        self.data = bytearray(data)
        off, _, self.w, self.h = struct.unpack_from("<4I", data, 0xB0 + 0x20 * index)
        self.start = off + 32

    def pixels(self):
        """Imagen en índices de 8 bits (256 x 64 para 128 x 32)."""
        gs = Gs()
        gs.write32(0, self.w // 64, self.w, self.h, self.data[self.start:self.start + 4 * self.w * self.h])
        return gs.read8(0, self.w // 32, 2 * self.w, 2 * self.h)

    def store(self, pixels):
        gs = Gs()
        gs.write8(0, self.w // 32, 2 * self.w, 2 * self.h, pixels)
        self.data[self.start:self.start + 4 * self.w * self.h] = gs.read32(0, self.w // 64, self.w, self.h)
        return bytes(self.data)
