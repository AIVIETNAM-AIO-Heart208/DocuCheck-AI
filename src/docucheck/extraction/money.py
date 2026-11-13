"""Lossless integer monetary parsing; fractional currencies require review."""

import re

TOKEN = r"(?<![\w/.,:-])-?\d+(?:[.,]\d+)*(?![\w/.,:-])"


def parse(text):
    if re.fullmatch(r"-?(?:\d+|\d{1,3}(?:[.,]\d{3})+)", text):
        return int(text.replace(",", "").replace(".", ""))
    for thousands, decimal in ((",", "."), (".", ",")):
        pattern = rf"-?(?:\d+|\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+){re.escape(decimal)}00"
        if re.fullmatch(pattern, text):
            return int(text.rsplit(decimal, 1)[0].replace(thousands, ""))
    return None
