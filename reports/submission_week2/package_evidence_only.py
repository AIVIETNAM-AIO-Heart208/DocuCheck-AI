"""Create the submission containing only the report and experiment evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'outputs/submission/DocuCheck_AI_Week2_FINAL_v3'
OUT = ROOT / 'outputs/submission/DocuCheck_AI_Week2_FINAL_v4'
ARCHIVE = OUT.with_suffix('.zip')
if OUT.exists() or ARCHIVE.exists():
    raise SystemExit('Target already exists.')

selected = [SOURCE / 'DocuCheck_AI_Week2_Report.pdf']
for folder in ('evidence/goal1', 'evidence/goal2', 'evidence/goal3', 'figures'):
    selected.extend(p for p in (SOURCE / folder).rglob('*') if p.is_file())
selected = [p for p in selected if p.name != 'closure_decision.json']
hashes = {}
for source in sorted(selected):
    relative = source.relative_to(SOURCE)
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    hashes[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == hashes[relative.as_posix()]
with zipfile.ZipFile(ARCHIVE, 'x', zipfile.ZIP_DEFLATED) as archive:
    for name in hashes:
        archive.write(OUT / name, name)
with zipfile.ZipFile(ARCHIVE) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(hashes)
    for name, digest in hashes.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert not any('manifest' in n.lower() or 'checklist' in n.lower() or 'report_quality' in n for n in archive.namelist())

# Verification stays in the working report folder, outside the submission.
result = {'archive': str(ARCHIVE.relative_to(ROOT)), 'file_count': len(hashes),
          'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
          'crc_and_hashes': 'passed', 'files': hashes}
(ROOT / 'reports/submission_week2/evidence/evidence_only_package_verification.json').write_text(
    json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
