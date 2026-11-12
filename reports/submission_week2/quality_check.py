"""Check the final report and protected inputs, without modifying those inputs."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

baseline = json.loads((HERE / 'evidence/protected_before.json').read_text(encoding='utf-8'))
changed = [p for p, old in baseline.items() if not (ROOT / p).is_file() or sha(ROOT / p) != old]
save('evidence/protected_after.json', {'date': '2026-11-06', 'files_checked': len(baseline), 'changed': changed})
authorized = json.loads((HERE / 'evidence/authorized_document_updates.json').read_text(encoding='utf-8'))
assert set(changed) == set(authorized), changed
assert all(sha(ROOT / p) == row['after_sha256'] and baseline[p] == row['before_sha256'] for p, row in authorized.items())
save('evidence/protected_after.json', {'date':'2026-11-06', 'files_checked':len(baseline), 'unchanged':len(baseline)-len(changed), 'authorized_document_updates':authorized, 'unexpected_changes':[]})

log = (HERE / 'main.log').read_text(encoding='utf-8', errors='replace')
bad = re.findall(r'Overfull \\[hv]box|Missing character:|undefined references|Citation .+ undefined|Reference .+ undefined', log)
assert not bad, bad
document = ET.parse(HERE / 'qa/bbox.html')
pages = document.findall('.//{*}page')
assert len(pages) == 11, len(pages)
stats = []
for i, page in enumerate(pages, 1):
    words = page.findall('.//{*}word')
    width, height = float(page.attrib['width']), float(page.attrib['height'])
    assert words
    for w in words:
        x0, y0, x1, y1 = [float(w.attrib[k]) for k in ('xMin', 'yMin', 'xMax', 'yMax')]
        assert 15 <= x0 <= x1 <= width-15 and 15 <= y0 <= y1 <= height-15, (i, w.text, w.attrib)
    text = ' '.join(w.text or '' for w in words)
    if i > 1:
        assert 'DOCUCHECK AI' in text and 'BÁO CÁO TUẦN 2' in text
        assert '06.11.2026' in text
    assert '\ufffd' not in text
    minimum_words = 30 if i == 1 else (100 if i == len(pages) else 200)
    assert len(words) > minimum_words
    stats.append({'pdf_page': i, 'words': len(words), 'a4': abs(width-595.28)<1 and abs(height-841.89)<1,
                  'render_sha256': sha(HERE / f'qa/review-page-{i:02d}.png')})

text = (HERE / 'qa/extracted.txt').read_text(encoding='utf-8')
required = ['20,6496%', '56,1786%', '60,8365%', '81,5953%', '9,59%', '33,87%',
            '137,7', '105,9', '207,7', '159,8', '4.265', '56.619', '11.584', 'còn bất định',
            'Tài liệu tham khảo', 'Nguyễn Văn Minh', 'Nguyễn Thành Trung']
assert all(s in text for s in required), [s for s in required if s not in text]
editorial_patterns = {
 'internal_filenames_or_paths': r'(?i)\b\S+\.(?:jsonl?|py|md|html|traineddata|tex|pdf)\b|(?:outputs|reports)/|C:/',
 'conversation_or_authoring_context': r'(?i)ChatGPT|Codex|OpenAI|assistant|prompt|workspace|người dùng|lượt biên tập|lượt lập báo cáo|nhóm cung cấp|ảnh OCR mô phỏng',
}
editorial_scan = {name: re.findall(pattern, text) for name, pattern in editorial_patterns.items()}
assert not any(editorial_scan.values()), editorial_scan
visual = json.loads((HERE / 'evidence/visual_review.json').read_text(encoding='utf-8'))
assert visual['pdf_sha256'] == sha(HERE/'main.pdf'), 'PDF changed: render and inspect all pages again before updating visual_review.json.'
save('evidence/pdf_qa.json', {'date': '2026-11-06', 'timezone': 'Asia/Saigon', 'pdf_sha256': sha(HERE/'main.pdf'),
 'page_count': len(pages), 'format': 'A4', 'pages': stats,
 'latex_log_errors': bad, 'text_landmarks': 'passed', 'text_inside_page_bounds': True,
 'editorial_scan': editorial_scan,
 'protected_files_unchanged': len(baseline)-len(changed),
 'visual_review': visual,
 'scope': 'Report QA only; no benchmark/test suite rerun; Goal 3 provenance remains limited as documented.'})
print(json.dumps({'pages': len(pages), 'protected_files_unchanged': len(baseline)-len(changed), 'status': 'passed'}, ensure_ascii=False))
