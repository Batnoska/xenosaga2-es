"""Arma el kit de publicación de la traducción en work/publicar.

  python tools/kit.py 0.9-beta            paquete, aplicador de Windows, LEEME y el .zip final
  python tools/kit.py 0.9-beta --probar   además aplica el parche con el .exe a las ISO
                                          originales y compara el resultado con work/ (y, con
                                          la Definitive Edition, con la versión en Python). Si
                                          existe iso_path_americana.txt (las ISO americanas sin
                                          undub, una por línea), las prueba también
  python tools/kit.py 0.9-beta --de 0.1-beta
                                          arma también el kit de la Definitive Edition: el mismo
                                          aplicador, con su casilla primero y marcada

Si está el repositorio de la Definitive Edition junto a este, el paquete la incluye (parche.py).

El aplicador de Windows (tools/aplicador: Aplicador.cs y la ventana, Ventana.cs) se compila con el
csc de .NET Framework 4, que ya viene con Windows, y lleva adentro el paquete y el arte de la ventana
(tools/aplicador/arte.py): el kit es un .exe y el LEEME. Para otros sistemas va también la versión
en Python (parche.py + x2iso.py + el paquete).
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "aplicador"))
import arte  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
TOOLS = os.path.join(ROOT, "tools")
SRC = os.path.join(TOOLS, "aplicador")
PUBLISH = os.path.join(ROOT, "work", "publicar")
PACKAGE = os.path.join(ROOT, "work", "xenosaga2_es.zip")
EXE = {"es": "Aplicar parche.exe", "de": "Apply patch.exe"}
OTHERS = {"es": "Otros sistemas (Python)", "de": "Other systems (Python)"}
NOMBRE = {"es": "Xenosaga Episode II en español", "de": "Xenosaga Episode II Definitive Edition"}


def csc():
    for fw in ("Framework64", "Framework"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Microsoft.NET", fw, "v4.0.30319", "csc.exe")
        if os.path.exists(path):
            return path
    sys.exit("no se encontró csc.exe de .NET Framework 4")


def con_definitiva():
    with zipfile.ZipFile(PACKAGE) as z:
        return "de.tsv" in z.namelist()


def compile_exe(version, out_exe, tmp, edicion="es"):
    """edicion: "es" (la de la traducción) o "de" (la de la Definitive Edition). El programa es el
    mismo; cambian el título, los créditos y qué casilla va primero y marcada."""
    version_cs = os.path.join(tmp, "Version.cs")
    with open(version_cs, "w", encoding="utf-8") as f:
        f.write("using System.Reflection;\n"
                f'[assembly: AssemblyTitle("{NOMBRE[edicion]}")]\n'
                f'[assembly: AssemblyProduct("{NOMBRE[edicion]}")]\n'
                f'[assembly: AssemblyInformationalVersion("{version}")]\n'
                f'static partial class Aplicador {{ const string Version = "{version}", Edicion = "{edicion}"; }}\n')
    arte_zip, diseno_cs, icono = arte.generar(version, os.path.join(tmp, "arte"), edicion, con_definitiva())
    cmd = [csc(), "/nologo", "/target:winexe", "/optimize+", f"/out:{out_exe}", f"/win32icon:{icono}",
           f"/resource:{PACKAGE},parche.zip", f"/resource:{arte_zip},arte.zip",
           "/r:System.IO.Compression.dll", "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll",
           os.path.join(SRC, "Aplicador.cs"), os.path.join(SRC, "Ventana.cs"), os.path.join(SRC, "Textos.cs"),
           diseno_cs, version_cs]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit("error al compilar el aplicador:\n" + r.stdout + r.stderr)
    print(f"{os.path.basename(out_exe)}: {os.path.getsize(out_exe) // 1024} KB")


def write_readme(version, path, fuente="LEEME.txt"):
    text = open(os.path.join(SRC, fuente), encoding="utf-8").read()
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


# Combinaciones de la Definitive Edition que se prueban: el .exe y la versión en Python tienen que
# armar la misma ISO. (disco, argumentos, con traducción, perfil, cómo termina el nombre)
COMBINACIONES = [
    (1, ["--perfil", "historia"], True, "historia", " (Español + Definitive)"),
    (2, ["--sin-traduccion", "--perfil", "definitiva"], False, "definitiva", " (Definitive)"),
]


def igual_que_python(exe, out, iso, args, traduccion, perfil, sufijo):
    code, log = run_exe(exe, "--salida", out, "--idioma", "es", *args, iso)
    result = os.path.join(out, os.path.splitext(os.path.basename(iso))[0] + sufijo + ".iso")
    if code or not os.path.exists(result):
        print(log)
        return False
    other = os.path.join(out, "python.iso")
    parche.apply(PACKAGE, iso, other, traduccion, parche.niveles_pedidos(PACKAGE, perfil, []))
    same = sha1_file(result) == sha1_file(other)
    for f in (result, other):
        os.remove(f)
    return same


def test(exe):
    """Aplica el parche a las ISO originales con el .exe y compara con las ISO de work/; con la
    Definitive Edition, compara también el .exe con la versión en Python."""
    out = os.path.join(PUBLISH, "prueba")
    os.makedirs(out, exist_ok=True)
    ok = True
    try:
        for disc, iso in enumerate(iso_paths(), 1):
            code, log = run_exe(exe, "--salida", out, "--idioma", "es", iso)
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
            code, log = run_exe(exe, "--salida", out, "--idioma", "es", result)  # una ISO ya traducida no se toca
            if code or "ya tiene la traducción" not in log:
                print("ISO ya traducida: respuesta inesperada\n" + log)
                ok = False
            if disc == 1 and con_definitiva():
                # a una ISO ya traducida se le puede sumar solo la Definitive Edition
                same = igual_que_python(exe, out, result, ["--sin-traduccion", "--perfil", "comodidad"],
                                        False, "comodidad", " (Definitive)")
                print(f"disco 1 ya traducido + comodidad: {'igual en Windows y en Python' if same else 'DISTINTA'}")
                ok &= same
            os.remove(result)
        # La ISO americana sin undub tiene cada volumen partido en archivos de 1 GB (el undub, en
        # uno solo): si están en iso_path_americana.txt, también se prueban.
        if os.path.exists(os.path.join(ROOT, "iso_path_americana.txt")):
            for disc, iso in enumerate(iso_paths("iso_path_americana.txt"), 1):
                same = igual_que_python(exe, out, iso, [], True, None, " (Español)")
                print(f"disco {disc} americano: {'igual en Windows y en Python' if same else 'DISTINTA'}")
                ok &= same
        if con_definitiva():
            for disc, args, traduccion, perfil, sufijo in COMBINACIONES:
                same = igual_que_python(exe, out, iso_paths()[disc - 1], args, traduccion, perfil, sufijo)
                que = ("traducción + " if traduccion else "") + perfil
                print(f"disco {disc}, {que}: {'igual en Windows y en Python' if same else 'DISTINTA'}")
                ok &= same
        code, log = run_exe(exe, "--salida", out, "--idioma", "es", os.path.join(SRC, "LEEME.txt"))
        if code == 0 or "No se puede usar" not in log:
            print("archivo que no es ISO: respuesta inesperada\n" + log)
            ok = False
        ok &= captura(exe, "captura")
    finally:
        shutil.rmtree(out, ignore_errors=True)
    print("prueba: " + ("OK" if ok else "FALLÓ"))
    return ok


def captura(exe, nombre):
    """La ventana: que cargue el arte y se dibuje (deja varias capturas en work/publicar)."""
    path = os.path.join(PUBLISH, nombre + ".png")
    code, log = run_exe(exe, "--captura", path)
    if code or not os.path.exists(path):
        print("la ventana no se pudo dibujar\n" + log)
        return False
    print(f"ventana: {path}")
    return True


def armar(version, edicion, tmp):
    """La carpeta del kit de una edición, con su .exe, los LEEME y la versión en Python."""
    folder = os.path.join(PUBLISH, f"Xenosaga2_{edicion.upper()}_v{version}")
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(os.path.join(folder, OTHERS[edicion]))
    exe = os.path.join(folder, EXE[edicion])
    compile_exe(version, exe, tmp, edicion)
    write_readme(version, os.path.join(folder, "LEEME.txt"))
    write_readme(version, os.path.join(folder, "README.txt"), "README.txt")
    for src in (os.path.join(TOOLS, "parche.py"), os.path.join(TOOLS, "x2iso.py"), PACKAGE):
        shutil.copy2(src, os.path.join(folder, OTHERS[edicion]))
    return folder, exe


def comprimir(folder):
    archive = folder + ".zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(folder):
            for f in files:
                path = os.path.join(base, f)
                z.write(path, os.path.relpath(path, PUBLISH))
    print(f"{archive}: {os.path.getsize(archive) // 1024} KB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="por ejemplo 0.9-beta")
    ap.add_argument("--probar", action="store_true")
    ap.add_argument("--de", metavar="VERSION", help="arma también el kit de la Definitive Edition")
    args = ap.parse_args()
    parche.create(PACKAGE)
    if args.de and not con_definitiva():
        sys.exit("--de: no está el repositorio de la Definitive Edition")
    tmp = os.path.join(PUBLISH, "tmp")
    os.makedirs(tmp, exist_ok=True)
    kits = [armar(args.version, "es", tmp)]
    if args.de:
        kits.append(armar(args.de, "de", tmp))
    shutil.rmtree(tmp)
    if args.probar:
        if not test(kits[0][1]):
            sys.exit(1)
        if args.de and not captura(kits[1][1], "captura_de"):
            sys.exit(1)
    for folder, _ in kits:
        comprimir(folder)


if __name__ == "__main__":
    main()
