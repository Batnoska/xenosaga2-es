"""Lectura y reconstrucción de las ISO de Xenosaga Episode II (PS2, NTSC-U, dos DVD5).

Estructura del disco:
  - ISO9660 (con puente UDF que el juego no usa). En la raíz: SYSTEM.CNF, el
    ejecutable (SLUS_208.92 / SLUS_211.33), OV01.OVL, OV02.OVL, IOP/.
  - "Volúmenes" de datos: un índice XENOSAGA.g0 seguido, contiguo en el disco,
    de su parte de datos XENOSAGA.g1. Los sectores del índice se cuentan desde
    el inicio de XENOSAGA.g0.
      g=0: datos comunes (idéntico en los dos discos)
      g=1: videos y voces del disco 1; g=2: los del disco 2

Formato del índice (distinto del Episode I: cada nombre se guarda como
diferencia de otro):
  byte 0: tamaño del índice en sectores
  entradas hasta un byte 0; L = primer byte, n = L & 0x3F (cabecera + nombre)
    archivo: [L][P][nombre: n-2 bytes][sector u24][tamaño u32] (+u24 extra si L & 0x40)
    carpeta: [0x80|L][subir][P][nombre: n-3 bytes]
  P = 0: nombre completo (terminado en 0). Si no, se toma el nombre de
  referencia y se sobrescribe desde len(ref) - ((P >> 4) + 1) con los
  P & 0x0F bytes guardados. Referencia: para un archivo, el archivo anterior;
  para una carpeta, la que se cierra al "subir" (subir = niveles que se
  cierran, contando la carpeta actual; 0 = subcarpeta nueva).

Uso:
  python tools/x2iso.py list 0
  python tools/x2iso.py extract 0 work/extract/0 [--match 'ziggy_acf/*.sbl']
  python tools/x2iso.py extract-iso work/extract/iso
"""
import argparse
import fnmatch
import os
import struct
import sys

SECTOR = 2048
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iso_paths(archivo="iso_path.txt"):
    """Rutas de las ISO originales, una por disco, desde iso_path.txt (o el archivo indicado)."""
    with open(os.path.join(ROOT, archivo), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def sectors(size):
    return (size + SECTOR - 1) // SECTOR


class Entry:
    __slots__ = ("path", "sector", "size", "extra", "field_pos")

    def __init__(self, path, sector, size, extra, field_pos):
        self.path, self.sector, self.size, self.extra, self.field_pos = path, sector, size, extra, field_pos


def parse_index(data):
    entries, pos, prev_file, stack = [], 1, b"", []

    def apply(ref, P, stored):
        if P == 0:
            return stored.split(b"\0")[0]
        start = len(ref) - ((P >> 4) + 1)
        name = ref[:start] + stored + ref[start + len(stored):]
        return name.split(b"\0")[0]

    while pos < len(data):
        L = data[pos]
        if L == 0:
            break
        n = L & 0x3F
        if L & 0x80:
            up, P = data[pos + 1], data[pos + 2]
            depth = len(stack) - up
            ref = stack[depth] if up else b""
            stack = stack[:depth] + [apply(ref, P, data[pos + 3:pos + n])]
            pos += n
            continue
        name = apply(prev_file, data[pos + 1], data[pos + 2:pos + n])
        prev_file = name
        pos += n
        sector, size = int.from_bytes(data[pos:pos + 3], "little"), struct.unpack_from("<I", data, pos + 3)[0]
        extra = None
        if L & 0x40:
            extra = int.from_bytes(data[pos + 7:pos + 10], "little")
        path = "/".join(s.decode("latin1") for s in stack + [name])
        entries.append(Entry(path, sector, size, extra, pos))
        pos += 10 if L & 0x40 else 7
    return entries


class Iso:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        pvd = self.read_sectors(16, 1)
        assert pvd[1:6] == b"CD001", "no es una ISO9660"
        root_lba, root_len = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]
        self.files = {}  # nombre -> (lba, tamaño, offset del registro en la ISO)
        d = self.read_sectors(root_lba, sectors(root_len))
        p = 0
        while p < len(d):
            n = d[p]
            if n == 0:
                p = (p // SECTOR + 1) * SECTOR
                continue
            name = d[p + 33:p + 33 + d[p + 32]].decode("latin1").split(";")[0]
            if name not in ("\0", "\1"):
                lba, size = struct.unpack_from("<I", d, p + 2)[0], struct.unpack_from("<I", d, p + 10)[0]
                self.files[name] = (lba, size, root_lba * SECTOR + p)
            p += n
        self.executable = next(n for n in self.files if n.startswith("SLUS_"))
        self.groups = sorted(int(n[-2]) for n in self.files if n.startswith("XENOSAGA.") and n.endswith("0"))

    def read_sectors(self, lba, count):
        self.f.seek(lba * SECTOR)
        return self.f.read(count * SECTOR)

    def read_file(self, name):
        lba, size, _ = self.files[name]
        self.f.seek(lba * SECTOR)
        return self.f.read(size)


class Volume:
    """Volumen g: el índice XENOSAGA.g0 y su parte de datos XENOSAGA.g1."""

    def __init__(self, iso, group):
        self.iso, self.group = iso, group
        self.index_name, self.data_name = f"XENOSAGA.{group}0", f"XENOSAGA.{group}1"
        self.base = iso.files[self.index_name][0]
        assert iso.files[self.data_name][0] == self.base + sectors(iso.files[self.index_name][1])
        # La parte de datos puede ser varios archivos seguidos: la ISO original la corta en partes
        # de 1 GB (XENOSAGA.11, .12, .13...); las armadas con otras herramientas (el undub, por
        # ejemplo) suelen tener una sola. Lo que se agrega va al final de la última.
        self.data_names = sorted((n for n in iso.files if n[:-1] == f"XENOSAGA.{group}" and n[-1] != "0"),
                                 key=lambda n: iso.files[n][0])
        self.data_sectors = 0
        for n in self.data_names:
            lba, size, _ = iso.files[n]
            assert lba == self.base + sectors(iso.files[self.index_name][1]) + self.data_sectors, f"{n} no sigue al anterior"
            self.data_sectors += sectors(size)
        self.last_data = self.data_names[-1]
        self.index = iso.read_file(self.index_name)
        self.entries = parse_index(self.index)
        self.by_path = {e.path: e for e in self.entries}

    def read(self, entry):
        self.iso.f.seek((self.base + entry.sector) * SECTOR)
        return self.iso.f.read(entry.size)

    def find(self, pattern):
        return [e for e in self.entries if fnmatch.fnmatch(e.path, pattern)]


def _set_both_endian(buf, off, value):
    struct.pack_into("<I", buf, off, value)
    struct.pack_into(">I", buf, off + 4, value)


def build(iso_path, out_path, replacements, loose=None, log=print):
    """Escribe una ISO nueva con archivos reemplazados.

    replacements: {(grupo, ruta): bytes} para archivos de los volúmenes.
    loose: {nombre en la raíz: bytes} (ejecutable, overlays); deben tener el mismo tamaño.

    Un archivo que entra en sus sectores originales se escribe en el lugar; si
    no, se agrega al final de la parte de datos de su volumen (de la última, si
    está en varios archivos) y todo lo que sigue en el disco se corre. Se actualizan el índice, los registros ISO9660
    y el tamaño del volumen (el puente UDF queda como estaba: el juego y los
    emuladores leen ISO9660).
    """
    iso = Iso(iso_path)
    loose = loose or {}
    volumes = {g: Volume(iso, g) for g in iso.groups}
    in_place, appended, new_index = {}, {}, {}
    last = {vol.last_data: g for g, vol in volumes.items()}  # el archivo que crece en cada volumen
    for g, vol in volumes.items():
        index = bytearray(vol.index)
        end = sectors(iso.files[vol.index_name][1]) + vol.data_sectors
        tail = []
        for (rg, path), data in sorted((k, v) for k, v in replacements.items() if k[0] == g):
            e = vol.by_path[path]
            if sectors(len(data)) <= sectors(e.size):
                in_place[(vol.base + e.sector) * SECTOR] = (data, sectors(e.size) * SECTOR)
                sector = e.sector
            else:
                sector = end
                tail.append(data)
                end += sectors(len(data))
            index[e.field_pos:e.field_pos + 3] = sector.to_bytes(3, "little")
            struct.pack_into("<I", index, e.field_pos + 3, len(data))
        new_index[g] = bytes(index)
        appended[g] = tail
    for name, data in loose.items():
        lba, size, _ = iso.files[name]
        assert len(data) == size, f"{name}: el tamaño debe quedar igual"
        in_place[lba * SECTOR] = (data, sectors(size) * SECTOR)

    # Registros ISO9660 nuevos: cada parte de datos crece y lo que sigue se corre.
    grow = {g: sum(sectors(len(d)) for d in appended[g]) for g in volumes}
    layout = sorted(iso.files.items(), key=lambda kv: kv[1][0])
    shift, new_lba, new_size = 0, {}, {}
    for name, (lba, size, _) in layout:
        new_lba[name], new_size[name] = lba + shift, size
        if name in last:
            new_size[name] = size + grow[last[name]] * SECTOR
            shift += grow[last[name]]
    total_sectors = struct.unpack_from("<I", iso.read_sectors(16, 1), 80)[0] + shift

    src = iso.f
    with open(out_path, "w+b") as out:
        def copy(start, stop):
            src.seek(start)
            remaining = stop - start
            while remaining > 0:
                chunk = src.read(min(remaining, 16 << 20))
                if not chunk:
                    break
                out.write(chunk)
                remaining -= len(chunk)

        cursor = 0
        for name, (lba, size, _) in layout:
            if name not in last:
                continue
            stop = (lba + sectors(size)) * SECTOR
            copy(cursor, stop)
            for data in appended[last[name]]:
                out.write(data + bytes(sectors(len(data)) * SECTOR - len(data)))
            cursor = stop
        copy(cursor, os.path.getsize(iso_path))

        # Reemplazos en el lugar (en coordenadas de la ISO original, corridas).
        def moved(offset):
            lba = offset // SECTOR
            extra = 0
            for name, (flba, size, _) in layout:
                if name in last and lba >= flba + sectors(size):
                    extra += grow[last[name]]
            return offset + extra * SECTOR

        for offset, (data, room) in in_place.items():
            out.seek(moved(offset))
            out.write(data + bytes(room - len(data)))
        for g, data in new_index.items():
            out.seek(new_lba[volumes[g].index_name] * SECTOR)
            out.write(data)
        for name, (lba, size, rec) in iso.files.items():
            out.seek(rec)
            record = bytearray(out.read(34))
            _set_both_endian(record, 2, new_lba[name])
            _set_both_endian(record, 10, new_size[name])
            out.seek(rec)
            out.write(record)
        for lba in (16, 17):  # descriptor primario (y el siguiente, si es suplementario)
            out.seek(lba * SECTOR)
            head = out.read(6)
            if head[0] in (1, 2) and head[1:6] == b"CD001":
                out.seek(lba * SECTOR + 80)
                out.write(struct.pack("<I", total_sectors) + struct.pack(">I", total_sectors))
    log(f"{out_path}: {len(replacements)} archivos ({sum(len(t) for t in appended.values())} reubicados), "
        f"+{shift} sectores")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disco", type=int, default=1, help="1 o 2 (según iso_path.txt)")
    ap.add_argument("--iso", default=None, help="ruta a la ISO (por defecto, la de iso_path.txt)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("group", type=int)
    p = sub.add_parser("extract")
    p.add_argument("group", type=int)
    p.add_argument("outdir")
    p.add_argument("--match", default="*", help="patrón de rutas (ej: 'ziggy_acf/*.sbl')")
    p = sub.add_parser("extract-iso", help="extraer archivos sueltos (ejecutable, overlays)")
    p.add_argument("outdir")
    args = ap.parse_args()
    iso = Iso(args.iso or iso_paths()[args.disco - 1])
    if args.cmd == "extract-iso":
        os.makedirs(args.outdir, exist_ok=True)
        for name in iso.files:
            if "." in name and not name.startswith("XENOSAGA."):
                with open(os.path.join(args.outdir, name), "wb") as f:
                    f.write(iso.read_file(name))
        return
    vol = Volume(iso, args.group)
    if args.cmd == "list":
        out = sys.stdout
        for e in vol.entries:
            out.write(f"{e.path}\t{e.sector}\t{e.size}\t{'' if e.extra is None else e.extra}\n")
        return
    count = 0
    for e in vol.find(args.match):
        dest = os.path.join(args.outdir, *e.path.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(vol.read(e))
        count += 1
    print(f"{count} archivos extraídos en {args.outdir}")


if __name__ == "__main__":
    main()
