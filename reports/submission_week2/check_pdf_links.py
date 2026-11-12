"""Inspect URI actions in this generated PDF, including compressed object streams."""
from pathlib import Path
import json
import re
import zlib

base = Path(__file__).resolve().parent
raw = (base / 'main.pdf').read_bytes()
chunks = [raw]
for match in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', raw, re.S):
    try:
        chunks.append(zlib.decompress(match.group(1)))
    except zlib.error:
        pass
links = []
for chunk in chunks:
    for m in re.finditer(rb'/URI\s*(?:\(([^)]*)\)|<([0-9a-fA-F]+)>)', chunk):
        value = m.group(1) if m.group(1) is not None else bytes.fromhex(m.group(2).decode())
        links.append(value.decode('utf-8'))
expected = [
    'https://www.rivf2021-mc-ocr.vietnlp.com/',
    'https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method',
    'https://github.com/pbcquoc/vietocr#model-zoo',
    'https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html',
    'https://jitsi.github.io/jiwer/reference/process/',
]
missing = [url for url in expected if url not in links]
(base / 'evidence/pdf_links.json').write_text(json.dumps({
    'checked_date': '2026-11-06', 'uri_actions': links, 'missing_expected_urls': missing,
    'scope': 'PDF has URI actions to the five primary sources opened and inspected during source review.'
}, ensure_ascii=False, indent=2), encoding='utf-8')
assert not missing, {'missing': missing, 'found': links}
print(json.dumps({'expected_links': len(expected), 'uri_actions': len(links), 'status': 'passed'}))
