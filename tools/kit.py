"""Arma el kit de publicación de la traducción en work/publicar.

  python tools/kit.py 0.9-beta            paquete, aplicador de Windows, LEEME y el .zip final
  python tools/kit.py 0.9-beta --probar   además aplica el parche con el .exe a las ISO
                                          originales y compara el resultado con work/

El aplicador de Windows (tools/aplicador/Aplicador.cs) se compila con el csc de .NET Framework 4,
que ya viene con Windows, y lleva el paquete adentro: el kit es un .exe y el LEEME. Para otros
sistemas va también la versión en Python (parche.py + x2iso.py + el paquete).
"""
import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

import parche
from x2iso import ROOT, iso_paths

sys.stdout.reconfigure(encoding="utf-8")
TOOLS = os.path.join(ROOT, "tools")
SRC = os.path.join(TOOLS, "aplicador")
PUBLISH = os.path.join(ROOT, "work", "publicar")
PACKAGE = os.path.join(ROOT, "work", "xenosaga2_es.zip")
EXE = "Aplicar parche.exe"
OTHERS = "Otros sistemas (Python)"


def csc():
    for fw in ("Framework64", "Framework"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Microsoft.NET", fw, "v4.0.30319", "csc.exe")
        if os.path.exists(path):
            return path
    sys.exit("no se encontró csc.exe de .NET Framework 4")


def compile_exe(version, out_exe, tmp):
    version_cs = os.path.join(tmp, "Version.cs")
    with open(version_cs, "w", encoding="utf-8") as f:
        f.write("using System.Reflection;\n"
                '[assembly: AssemblyTitle("Xenosaga Episode II en español")]\n'
                '[assembly: AssemblyProduct("Xenosaga Episode II en español")]\n'
                f'[assembly: AssemblyInformationalVersion("{version}")]\n'
                f'static partial class Aplicador {{ const string Version = "{version}"; }}\n')
    cmd = [csc(), "/nologo", "/target:exe", "/optimize+", f"/out:{out_exe}", f"/resource:{PACKAGE},parche.zip",
           "/r:System.IO.Compression.dll", "/r:System.Windows.Forms.dll",
           os.path.join(SRC, "Aplicador.cs"), version_cs]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit("error al compilar el aplicador:\n" + r.stdout + r.stderr)
    print(f"{EXE}: {os.path.getsize(out_exe) // 1024} KB")


def write_readme(version, path):
    text = open(os.path.join(SRC, "LEEME.txt"), encoding="utf-8").read()
    text = text.replace("{version}", version).replace("{fecha}", datetime.date.today().isoformat())
    if "[COMPLETAR" in text:
        print("ojo: el LEEME todavía tiene partes [COMPLETAR ...]")
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:  # con BOM y CRLF para el Bloc de notas
        f.write(text)


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(16 << 20):
            h.update(chunk)
    return h.hexdigest()


def run_exe(exe, *args):
    r = subprocess.run([exe, *args], stdin=subprocess.DEVNULL, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def test(exe):
    """Aplica el parche a las ISO originales con el .exe y compara con las ISO de work/."""
    out = os.path.join(PUBLISH, "prueba")
    os.makedirs(out, exist_ok=True)
    ok = True
    try:
        for disc, iso in enumerate(iso_paths(), 1):
            code, log = run_exe(exe, "--salida", out, iso)
            result = os.path.join(out, os.path.splitext(os.path.basename(iso))[0] + " (Español).iso")
            expected = os.path.join(ROOT, "work", f"xenosaga2_es_disco{disc}.iso")
            same = code == 0 and os.path.exists(result) and sha1_file(result) == sha1_file(expected)
            print(f"disco {disc}, aplicador de Windows: {'idéntica a work/' if same else 'DISTINTA'}")
            if not same:
                print(log)
                ok = False
                continue
            other = os.path.join(out, "python.iso")
            parche.apply(PACKAGE, iso, other)
            same_py = sha1_file(other) == sha1_file(expected)
            print(f"disco {disc}, versión en Python: {'idéntica a work/' if same_py else 'DISTINTA'}")
            ok &= same_py
            os.remove(other)
            code, log = run_exe(exe, "--salida", out, result)  # una ISO ya traducida no se toca
            if code or "ya tiene la traducción" not in log:
                print("ISO ya traducida: respuesta inesperada\n" + log)
                ok = False
        code, log = run_exe(exe, "--salida", out, os.path.join(SRC, "LEEME.txt"))
        if code == 0 or "No se puede usar" not in log:
            print("archivo que no es ISO: respuesta inesperada\n" + log)
            ok = False
    finally:
        shutil.rmtree(out, ignore_errors=True)
    print("prueba: " + ("OK" if ok else "FALLÓ"))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="por ejemplo 0.9-beta")
    ap.add_argument("--probar", action="store_true")
    args = ap.parse_args()
    name = f"Xenosaga2_ES_v{args.version}"
    folder = os.path.join(PUBLISH, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(os.path.join(folder, OTHERS))

    parche.create(PACKAGE)
    tmp = os.path.join(PUBLISH, "tmp")
    os.makedirs(tmp, exist_ok=True)
    exe = os.path.join(folder, EXE)
    compile_exe(args.version, exe, tmp)
    shutil.rmtree(tmp)
    write_readme(args.version, os.path.join(folder, "LEEME.txt"))
    for src in (os.path.join(TOOLS, "parche.py"), os.path.join(TOOLS, "x2iso.py"), PACKAGE):
        shutil.copy2(src, os.path.join(folder, OTHERS))

    if args.probar and not test(exe):
        sys.exit(1)
    archive = folder + ".zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(folder):
            for f in files:
                path = os.path.join(base, f)
                z.write(path, os.path.relpath(path, PUBLISH))
    print(f"{archive}: {os.path.getsize(archive) // 1024} KB")


if __name__ == "__main__":
    main()
