def parse_header(line):
    parts = line.split(";")
    key = parts[0].strip()
    pdict = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.strip().split("=", 1)
            pdict[k.strip()] = v.strip()
    return key, pdict