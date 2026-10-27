"""Busca en todas las traducciones lo que una lectura humana puede pasar por alto.

  python work/revision_global.py            resumen por tipo
  python work/revision_global.py <tipo>     las entradas de ese tipo
"""
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, "tools")
import po

sys.stdout.reconfigure(encoding="utf-8")
CODES = re.compile(r"\$[^;]*;|<[^<>]{1,2}>|&\d\d|●")

CHECKS = {
    # regionalismos y voseo
    "regional": r"\b(nomás|no hay caso|dale\b|che\b|boludo|pibe|laburo|güey|chamo|pana|chévere|ahorita|platicar|"
                r"vale[.!]|guay|mola|chaval|tío\b|gilipollas|ordenador|móvil|coger|vosotros|os\b|"
                r"en lo de\b|buen día|darse vuelta|se dio vuelta|date vuelta|no cierra|tontorrón|"
                r"pileta|celular|computador\b|frutilla|manejar el auto)",
    "voseo": r"\b(sos|tenés|sabés|querés|podés|vení|mirá|andá|decime|fijate|escuchá|esperá|hacé|poné|"
             r"tomá|vos\b|contame|dejame|ayudame|avisame|decí|salí|corré|vamos a ver)\b",
    "recién": r"\brecién (llega|empez|termin|comenz|sal|vin|vol|lo |la |me |te |se |\w+[oó]\b)",
    "seguido": r"\b(muy )?seguido\b",
    "muletilla": r"(^|[.!?…] )(Digo|Este)(,|\.\.\.)",
    "chicos": r"\bchic[oa]s?\b",
    "acentos viejos": r"\b(sólo|éste|ésta|éstos|éstas|ése|ésa|aquél|fué|dió|vió|fé|tí|guión|truhán)\b",
    "palabra repetida": r"\b(\w{2,}) \1\b",
    "a el / de el": r"\b(a|de) el\b",
    "por que/porque": r"\b(por que [a-záéíóú]+ (no|si)|el porque\b|porqué\b)",
    "haber/a ver": r"\b(haber si|a ver sido|a ver que)\b",
    "elipsis unicode": r"…",
    "comillas tipográficas": r"[“”«»]",
    "espacio raro": r" [,.;:?!]| {2,}|^\s|\s$",
    "usted y tú juntos": None,
}
TU = re.compile(r"\b(tienes|puedes|quieres|sabes|eres|estás|vienes|haces|dices|vas|te ayudo|contigo|tu\b|tus\b|"
                r"mira\b|ven\b|escucha\b|dime\b|espera\b|toma\b)", re.I)
USTED = re.compile(r"\b(usted|ustedes)\b", re.I)


def main():
    found = defaultdict(list)
    for path in sorted(glob.glob("traduccion/*/*.po")) + ["traduccion/nombres.po"]:
        name = os.path.relpath(path, "traduccion")[:-3].replace(os.sep, "/")
        for e in po.read(path)[1]:
            if not e.msgstr:
                continue
            text = CODES.sub("", e.msgstr)
            for kind, rx in CHECKS.items():
                if rx is None:
                    continue
                flags = re.I if kind not in ("palabra repetida", "muletilla") else re.I * (kind == "palabra repetida")
                for line in text.split("\n"):
                    if re.search(rx, line, flags | re.M):
                        if kind == "espacio raro" and re.search(rx, CODES.sub("", e.msgid.split("\n")[0])):
                            continue
                        found[kind].append((name, e))
                        break
            if USTED.search(text) and TU.search(text) and "ustedes" not in text.lower():
                found["usted y tú juntos"].append((name, e))
    if len(sys.argv) > 1:
        kind = " ".join(sys.argv[1:])
        for name, e in found.get(kind, []):
            print(f"== {name} {e.msgctxt}")
            print("   EN:", e.msgid.replace("\n", " / "))
            print("   ES:", e.msgstr.replace("\n", " / "))
    else:
        for kind in CHECKS:
            print(f"{len(found.get(kind, [])):5}  {kind}")


main()
