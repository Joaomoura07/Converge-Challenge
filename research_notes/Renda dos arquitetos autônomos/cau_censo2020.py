"""Tabula colunas de interesse do microdado público do CAU (Censo 2020)."""
import collections
import csv
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ROW = re.compile(rb'<row\b[^>]*\br="(\d+)"[^>]*>')
CELL = re.compile(rb'<c\s[^>]*\br="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)')
VALUE = re.compile(rb'<v>(.*?)</v>')

def iter_rows(archive):
    with archive.open("xl/worksheets/sheet1.xml") as sheet:
        remainder = b""
        while chunk := sheet.read(2 ** 20):
            blocks = (remainder + chunk).split(b"</row>")
            remainder = blocks.pop()
            for block in blocks:
                match = ROW.search(block)
                if match:
                    yield int(match[1]), block[match.end():]

def cell_value(attrs, body, strings):
    if not body:
        return ""
    match = VALUE.search(body)
    if match:
        v = match[1].decode()
        return strings[int(v)] if b't="s"' in attrs else v
    return ""

def summarize(path):
    sources = "G H I J K L M N O P Q R S".split()
    bands = "Z AA AB AC AD AE AF AG AH".split()
    groups = collections.defaultdict(collections.Counter)
    checks = collections.Counter()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        records = csv.reader(handle, delimiter="\t")
        next(records)
        for record in records:
            values = dict(zip(sources + bands, record))
            selected = {k for k, v in values.items() if v == "1"}
            valid = selected.intersection(sources[:-1])
            income = selected.intersection(bands[:-1])
            count = int(record[-1])
            checks["source_yes" if valid else "source_missing"] += count
            checks["single_income" if len(income) == 1 else "income_missing_or_multi"] += count
            if len(valid) > 1:
                checks["multi_source"] += count
            if "L" in valid and valid - {"L"}:
                checks["multi_among_AU_self_employed"] += count
            memberships = ["Todos"]
            if valid:
                memberships.append("Fonte válida")
            if "L" in valid:
                memberships.append("Autônomos A&U, com ou sem outras fontes")
            if valid and "L" not in valid:
                memberships.append("Demais, sem autonomia A&U")
            if valid & {"L", "M"}:
                memberships.append("Autônomos A&U ou outra área")
            if valid and not valid & {"L", "M"}:
                memberships.append("Sem autonomia declarada em qualquer área")
            if valid == {"L"}:
                memberships.append("Somente autônomo A&U")
            if valid in ({"I"}, {"J"}):
                memberships.append("Somente assalariado A&U (privado ou público)")
            if valid == {"I"}:
                memberships.append("Somente assalariado privado A&U")
            if valid == {"J"}:
                memberships.append("Somente assalariado público A&U")
            if valid == {"N"}:
                memberships.append("Somente empresário A&U")
            for group in memberships:
                groups[group][next(iter(income)) if len(income) == 1 else "AH"] += count
    print(dict(checks))
    print("Grupo\tTotal\t" + "\t".join(bands))
    for name, counts in groups.items():
        print(name, counts.total(), *(counts[c] for c in bands), sep="\t")

def main():
    if sys.argv[1] == "--summary":
        return summarize(sys.argv[2])
    with zipfile.ZipFile(sys.argv[1]) as archive:
        sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in si.iter(MAIN+"t")) for si in sst]
        rows = iter_rows(archive)
        if len(sys.argv) < 3:
            for row_num, body in rows:
                if row_num > 3:
                    break
                fields = [(c.decode(), cell_value(attrs, val, strings)) for c, attrs, val in CELL.findall(body)]
                print(row_num, fields)
            return
        selected = [col.encode() for col in sys.argv[2:]]
        codes = b"|".join(selected)
        cell_filter = re.compile(rb'<c\s[^>]*\br="(' + codes + rb')\d+"([^>]*?)(?:/>|>(.*?)</c>)')
        counts = collections.Counter()
        for row_num, body in rows:
            if row_num < 4:
                continue
            lookup = {c: cell_value(attrs, val, strings) for c, attrs, val in cell_filter.findall(body)}
            values = tuple(lookup.get(col, "") for col in selected)
            counts[values] += 1
        print("Registros:", counts.total())
        for values, count in counts.most_common():
            print(*values, count, sep="\t")

if __name__ == "__main__":
    main()
