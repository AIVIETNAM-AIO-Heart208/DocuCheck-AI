"""Select reproducible new receipts and split them into sequential demo batches."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / 'outputs/ocr_to_qwen/invoice_total_fix/run_20261113'


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/processed/manifest.jsonl')
    parser.add_argument('--dataset-root', type=Path, default=ROOT / 'data/mcocr')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--exclude-manifest', action='append', type=Path, default=[])
    args = parser.parse_args()
    if args.count < 1:
        parser.error('--count must be positive')
    excluded_ids, excluded_groups = set(), set()
    sources = [PREVIOUS / 'old_v2/manifest.jsonl', PREVIOUS / 'new_v2/manifest.jsonl', *args.exclude_manifest]
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(f'Exclusion manifest not found: {path}')
        for row in read_rows(path):
            excluded_ids.add(row['image_id'])
            excluded_groups.add(row.get('checksum_sha256') or row['image_path'])
    eligible = []
    seen = set(excluded_groups)
    for row in sorted(read_rows(args.manifest), key=lambda value: value['image_id']):
        group = row.get('checksum_sha256') or row['image_path']
        if row.get('split') != 'internal_dev' or row['image_id'] in excluded_ids or group in seen:
            continue
        if not (args.dataset_root / row['image_path']).is_file():
            continue
        if not row.get('image_width') or not row.get('image_height'):
            continue
        seen.add(group)
        eligible.append(row)
    if len(eligible) < args.count:
        raise ValueError(f'Only {len(eligible)} unique eligible images for count={args.count}')
    selected = random.Random(args.seed).sample(eligible, args.count)
    # Refuse reuse: keep the receipt selection frozen and preserve existing experiments.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    selection = {'seed':args.seed, 'count':args.count,
                 'policy':'Unique internal_dev image groups, excluding five previous receipts; no label-based selection',
                 'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                 'excluded_manifests':[str(p) for p in sources],
                 'images':[{key:row.get(key) for key in ('image_id','image_path','checksum_sha256','split')} for row in selected]}
    (args.output_dir / 'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
    all_rows = ''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in selected)
    (args.output_dir / 'manifest.jsonl').write_text(all_rows,encoding='utf-8')
    links = []
    for offset in range(0,len(selected),3):
        batch = args.output_dir / f'batch_{offset//3+1:02d}'
        batch.mkdir()
        rows = selected[offset:offset+3]
        (batch / 'manifest.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
        links.append(f'<li><a href="{batch.name}/demo.html">{html.escape(batch.name)}: {len(rows)} receipts</a></li>')
    (args.output_dir / 'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>OCR → Qwen test</h1><p>Run each batch before opening its demo link.</p><ul>'+''.join(links)+'</ul>',encoding='utf-8')
    print(f'Prepared {len(selected)} new receipts in {len(links)} batches: {args.output_dir}')
    print('Preparation only: OCR and Qwen have not run.')


if __name__ == '__main__':
    main()
