"""Lossless integer monetary parsing; fractional currencies require review."""

import re

SPACE = " \u00a0\u202f"
TOKEN = r"(?<![\w/.,:-])-?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)|\d+(?:[.,]\d+)*)(?=$|[^\w/.,:-]|(?:[d\u0111\u20ab]|[Vv][Nn][Dd])\b)"


def parse(text):
    if re.fullmatch(r"-?\d{1,3}(?:[ \u00a0\u202f]\d{3})+", text):
        return int(re.sub(r"[ \u00a0\u202f]", "", text))
    if re.fullmatch(r"-?(?:\d+|\d{1,3}(?:[.,]\d{3})+)", text):
        return int(text.replace(",", "").replace(".", ""))
    for thousands, decimal in ((",", "."), (".", ",")):
        pattern = rf"-?(?:\d+|\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+){re.escape(decimal)}00"
        if re.fullmatch(pattern, text):
            return int(text.rsplit(decimal, 1)[0].replace(thousands, ""))
    return None
