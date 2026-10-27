"""Comprueba que las ISO traducidas traen las texturas de graficos.py y los parches de código y
datos (ejecutable, OV01.OVL, OV02.OVL)."""
import sys
sys.path.insert(0, 'tools')
import graficos
import textos
from x2iso import Iso, Volume, iso_paths
iso0 = Iso(iso_paths()[0])
orig = Volume(iso0, 0)
expected = graficos.replacements(lambda g, path: orig.read(orig.by_path[path]))
exe0 = iso0.read_file(iso0.executable)
patched = {  # archivo de la raíz: función que, sobre el original, da lo que tiene que haber en lo que cambia
    "OV01.OVL": graficos.patch_ov01(iso0.read_file("OV01.OVL")),
    "OV02.OVL": textos.patch_messages(iso0.read_file("OV02.OVL"), exe0),
}
for disc in (1, 2):
    iso = Iso(f'work/xenosaga2_es_disco{disc}.iso')
    vol = Volume(iso, 0)
    for (g, path), data in expected.items():
        got = vol.read(vol.by_path[path])
        print(f'disco {disc} {path}: {"OK" if got == data else "DISTINTO"} ({len(got)} bytes)')
    for name, data in patched.items():
        got = iso.read_file(name)
        print(f'disco {disc} {name}: {"OK" if got == data else "DISTINTO"} ({len(got)} bytes)')
    # el ejecutable también lleva los textos sueltos: se comprueban solo los parches de graficos
    exe = iso.read_file(iso.executable)
    pos, _, code = graficos.save_load_code()
    ok = exe[pos:pos + len(code)] == code and all(
        int.from_bytes(exe[p:p + 2], "little") == new for p, (_, new) in graficos.EXE_PATCHES.items())
    print(f'disco {disc} {iso.executable} (parches de graficos): {"OK" if ok else "DISTINTO"}')
