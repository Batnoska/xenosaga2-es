"""Vista para la revisión de diálogos: inglés y español lado a lado, con quién habla.

  python work/dialogos.py escenas/sc8001 [escenas/sc8002 ...]
  python work/dialogos.py -c escenas/sc8001 ...    formato compacto (dos líneas por entrada)
"""
import sys

sys.path.insert(0, "tools")
import po

sys.stdout.reconfigure(encoding="utf-8")


def speaker(entry):
    for c in entry.comments:
        if c.startswith("habla: "):
            return c[7:]
        if c.startswith("tiempo "):
            return c[7:]
    return ""


compact = sys.argv[1] == "-c"
for name in sys.argv[1 + compact:]:
    print(f"##### {name}")
    for e in po.read(f"traduccion/{name}.po")[1]:
        en, es = e.msgid.replace("\n", " / "), e.msgstr.replace("\n", " / ")
        if compact:
            print(f"{e.msgctxt} [{speaker(e)}] {en}\n    {es}")
        else:
            print(f"{e.msgctxt} [{speaker(e)}]")
            print("  EN:", en)
            print("  ES:", es)
