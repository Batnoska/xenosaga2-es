"""Lectura y escritura mínima de archivos .po (gettext) para Poedit."""
import re


def _quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t").replace("\n", "\\n") + '"'


def _field(name, value):
    parts = re.findall(r"[^\n]*\n|[^\n]+$", value)
    if len(parts) <= 1:
        return f"{name} {_quote(value)}\n"
    return f'{name} ""\n' + "".join(_quote(p) + "\n" for p in parts)


class Entry:
    def __init__(self, msgctxt, msgid, msgstr="", comments=(), fuzzy=False):
        self.msgctxt, self.msgid, self.msgstr = msgctxt, msgid, msgstr
        self.comments, self.fuzzy = list(comments), fuzzy


def write(path, header, entries):
    """header: dict de campos de cabecera."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write('msgid ""\nmsgstr ""\n')
        for k, v in header.items():
            f.write(_quote(f"{k}: {v}\n") + "\n")
        for e in entries:
            f.write("\n")
            for c in e.comments:
                f.write(f"#. {c}\n")
            if e.fuzzy:
                f.write("#, fuzzy\n")
            f.write(_field("msgctxt", e.msgctxt))
            f.write(_field("msgid", e.msgid))
            f.write(_field("msgstr", e.msgstr))


def _unquote(s):
    s = s.strip()[1:-1]
    return re.sub(r'\\(.)', lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def read(path):
    """Devuelve (cabecera como dict, lista de Entry)."""
    header, entries = {}, []
    blocks = open(path, encoding="utf-8").read().split("\n\n")
    for block in blocks:
        comments, fuzzy, fields, current = [], False, {}, None
        for line in block.splitlines():
            if line.startswith("#."):
                comments.append(line[3:])
            elif line.startswith("#,"):
                fuzzy = "fuzzy" in line
            elif line.startswith("#"):
                continue
            elif line.startswith('"'):
                fields[current] += _unquote(line)
            elif line.strip():
                current, value = line.split(" ", 1)
                fields[current] = _unquote(value)
        if "msgid" not in fields:
            continue
        if fields["msgid"] == "" and "msgctxt" not in fields:
            for hl in fields.get("msgstr", "").splitlines():
                if ": " in hl:
                    k, v = hl.split(": ", 1)
                    header[k] = v
            continue
        entries.append(Entry(fields.get("msgctxt", ""), fields["msgid"], fields.get("msgstr", ""),
                             comments, fuzzy))
    return header, entries
