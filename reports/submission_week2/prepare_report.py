"""Prepare figures and read-only evidence checks; never run OCR/evaluation."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'outputs/ocr/week2'
G1 = BASE / 'goal1_20261105'
G2 = BASE / 'goal2_20261105_corrected'
REV = BASE / 'goal2_20261105_review_final'
G1REV = BASE / 'goal1_20261106_review_final'
for name in ('figures', 'evidence', 'qa'):
    (HERE / name).mkdir(exist_ok=True)

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Preserve a baseline of every existing file in the evidence bundles and Week 1.
protected = [ROOT / 'reports/submission1_week1', BASE, ROOT / 'docs', ROOT / 'src', ROOT / 'tests']
baseline_path = HERE / 'evidence/protected_before.json'
if not baseline_path.exists():
    baseline = {p.relative_to(ROOT).as_posix(): digest(p) for folder in protected
                for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for name in ('manifest.jsonl', 'recognition_manifest.jsonl'):
        p = ROOT / 'data/processed' / name
        if p.exists():
            baseline[p.relative_to(ROOT).as_posix()] = digest(p)
    save('evidence/protected_before.json', baseline)

checks = []
inventories = {}
for folder in (G1, G2, REV, G1REV):
    inventory = read(folder / 'artifact_manifest.json')
    if isinstance(inventory, dict) and 'files' in inventory:
        inventory = {r['path']: r['sha256'] for r in inventory['files']}
    if isinstance(inventory, dict) and all(isinstance(v, str) for v in inventory.values()):
        failures = [name for name, sha in inventory.items()
                    if not (folder / name).exists() or digest(folder / name) != sha]
        inventories[folder.name] = {'checked': len(inventory), 'mismatches': failures}
        assert not failures, (folder, failures)

metrics = {}
for split in ('official_train', 'official_val'):
    m = read(G1 / split / 'metrics.json')
    rows = [json.loads(x) for x in (G1 / split / 'per_crop_metrics.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == m['evaluated_crops']
    assert math.isclose(m['cer'], m['character_errors'] / m['ground_truth_characters'])
    assert math.isclose(m['wer'], m['word_errors'] / m['ground_truth_words'])
    assert math.isclose(m['exact_match_rate'], m['exact_match_crops'] / len(rows))
    for key, field in [('character_errors', 'char_errors'), ('word_errors', 'word_errors'),
                       ('ground_truth_characters', 'gt_characters'), ('ground_truth_words', 'gt_words')]:
        assert sum(r[field] for r in rows) == m[key]
    for key, filename in [('predictions', 'predictions.jsonl'), ('runtime', 'runtime.json')]:
        assert digest(G1 / split / filename) == m['input_sha256'][key]
    assert digest(ROOT / 'data/processed/recognition_manifest.jsonl') == m['input_sha256']['manifest']
    metrics[split] = m
    checks.append(f'{split}: saved per-crop sums, aggregate ratios, counts and input hashes agree')

psm = list(csv.DictReader((G2 / 'comparison.csv').open(encoding='utf-8')))
for r in psm:
    assert math.isclose(float(r['cer']), int(r['character_errors']) / int(r['ground_truth_characters']))
    assert math.isclose(float(r['wer']), int(r['word_errors']) / int(r['ground_truth_words']))
    assert int(r['ground_truth_characters']) == 56619 and int(r['ground_truth_words']) == 11584
    assert int(r['images_succeeded']) == 231
checks.append('Corrected PSM comparison: saved numerators, denominators and ratios agree')

review = read(REV / 'review_cases.json')
crop_review = read(G1REV / 'review_cases.json')
assert len(review) == 20 and len(crop_review) == 24
assert collections.Counter(r['cause'] for r in crop_review) == read(G1REV / 'review_summary.json')['cause_counts']
g3 = [dict(engine='VietOCR', version='0.3.13', model='vgg_transformer', cer=9.59, wer=33.87, empty=0, seconds=137.7, ms=105.9),
      dict(engine='Tesseract', version='5.3.4', model='vie.traineddata; PSM 7', cer=19.51, wer=55.49, empty=5, seconds=85.7, ms=65.9),
      dict(engine='PaddleOCR', version='3.7.0', model='latin_PP-OCRv5_mobile_rec', cer=17.44, wer=63.03, empty=5, seconds=207.7, ms=159.8)]
save('evidence/goal3_team_data.json', {'source': 'User supplied report, copied in attached request',
     'independently_verified': False, 'crops': 1300, 'gt_characters': 23739, 'gt_tokens': 4815, 'rows': g3,
     'historical_doc_ms': {'VietOCR': 85.0, 'Tesseract': 65.2, 'PaddleOCR': 99.8},
     'runtime_note': 'Historical document gives different latency. Referenced engine comparison bundle is absent; no run-level reconciliation possible.'})

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
    'axes.spines.right': False, 'axes.labelcolor': '#17324D', 'text.color': '#20262D', 'pdf.fonttype': 42})
colors = ['#217E87', '#6E8295', '#C2833B']
fig, axes = plt.subplots(1, 2, figsize=(8.3, 2.7), layout='constrained')
for ax, metric, limit in zip(axes, ('cer', 'wer'), (25, 75)):
    bars = ax.barh([r['engine'] for r in g3], [r[metric] for r in g3], color=colors, height=.56)
    ax.invert_yaxis()
    ax.set_xlim(0, limit)
    ax.set_xlabel(metric.upper() + ' (%) · thấp hơn tốt hơn')
    ax.grid(axis='x', alpha=.18)
    ax.set_axisbelow(True)
    for bar, r in zip(bars, g3):
        ax.text(bar.get_width()+limit*.02, bar.get_y()+bar.get_height()/2,
                f'{r[metric]:.2f}'.replace('.', ','), va='center', fontsize=10)
fig.savefig(HERE / 'figures/engine_metrics.pdf', bbox_inches='tight')
plt.close(fig)

fig, ax = plt.subplots(figsize=(8.3, 3.0), layout='constrained')
chosen = [review[i-1] for i in (1, 5, 7)]
for j, (mode, col) in enumerate(zip(('6', '4', '11'), colors)):
    vals = [c['measurements'][mode]['cer']*100 for c in chosen]
    bars = ax.bar([i+(j-1)*.24 for i in range(3)], vals, width=.22, color=col, label='PSM '+mode)
    ax.bar_label(bars, labels=[f'{v:.1f}'.replace('.', ',') for v in vals], fontsize=9, padding=3)
ax.set_xticks(range(3), ['Ca 01 · PSM 4 phục hồi chữ', 'Ca 05 · PSM 4 mất phần đầu', 'Ca 07 · PSM 11 tăng độ phủ'])
ax.set_ylim(0, 116)
ax.set_ylabel('CER từng ảnh (%)')
ax.legend(ncols=3, loc='upper center', frameon=False)
ax.grid(axis='y', alpha=.18)
ax.set_axisbelow(True)
fig.savefig(HERE / 'figures/psm_cases.pdf', bbox_inches='tight')
plt.close(fig)

sources = [ROOT / 'docs' / name for name in ('WEEK2_REPORT.md', 'WEEK2_RECOGNITION_PROTOCOL.md',
 'PSM_COMPARISON_REPORT.md', 'PSM_CORRECTED_PROTOCOL.md', 'GOAL3_OCR_BASELINE.md', 'PIPELINE.md')]
sources += [G1 / 'official_train/metrics.json', G1 / 'official_val/metrics.json', G1 / 'audit.json',
 G1REV / 'review_summary.json', G2 / 'comparison.csv', G2 / 'paired_analysis.json',
 REV / 'review_cases.json', REV / 'review_summary.json', REV / 'focused_trace.json']
save('evidence/source_hashes.json', {p.relative_to(ROOT).as_posix(): digest(p) for p in sources})
save('evidence/report_checks.json', {'date': '2026-11-06', 'mode': 'Read saved artifacts; no inference/evaluation rerun',
 'checks': checks, 'inventories': inventories, 'goal1': metrics, 'goal2': psm,
 'goal1_review': read(G1REV / 'review_summary.json'), 'goal2_review': read(REV / 'review_summary.json'),
 'historical_goal1_verifier_checks': len(read(G1 / 'verification.json')['checks']),
 'goal3_independently_verified': False,
 'illustrations': 'Plots of saved measurements only; no raw receipt image/transcript republished; source terms not established.'})
print(json.dumps({'checks': checks, 'inventories': inventories}, ensure_ascii=False))
