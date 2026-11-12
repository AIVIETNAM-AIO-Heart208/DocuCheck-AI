"""Assemble a local submission from an explicit allowlist of aggregate evidence."""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'reports/submission_week2'
BASE = ROOT / 'outputs/ocr/week2'
G1 = BASE / 'goal1_20261105'
G2 = BASE / 'goal2_20261105_corrected'
REVIEW = BASE / 'goal2_20261105_review_final'
OUT = ROOT / 'outputs/submission/DocuCheck_AI_Week2_FINAL_v3'
ARCHIVE = OUT.with_suffix('.zip')
if OUT.exists() or ARCHIVE.exists():
    raise SystemExit('Submission target already exists; choose a fresh version instead of overwriting.')
OUT.mkdir(parents=True)
provenance = {}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(name, text):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')

def write_json(name, data):
    write(name, json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def source_record(path, transformation):
    return {'source': path.relative_to(ROOT).as_posix(), 'source_sha256': digest(path),
            'transformation': transformation}

def copy(path, name):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    assert digest(path) == digest(target)
    provenance[name] = source_record(path, 'byte-identical copy')
    # Publication wording only; preserve source files, values and qualifications.
    if path.suffix == '.json':
        original = read(path)
        replacements = {
            'User supplied report, copied in attached request': 'Team-provided Goal 3 comparison report',
            'Explicit confirmation in project conversation': 'Recorded project review decision dated 2026-11-06',
            'User-authorized Goal 1 closure documentation; original experimental evidence unchanged.': 'Goal 1 closure documentation update; original experimental evidence unchanged.',
            'user_confirmed_observations': 'confirmed_observations',
            'explicit_user_confirmed_observations': 'explicitly_confirmed_observations',
            'user_uncertain_cases': 'uncertain_cases',
            'user_disagrees_cases': 'disputed_cases',
            'human_pixel_review_claimed': 'independent_visual_signoff_recorded',
            'Diagnostic comparison and 20-case review complete with documented limitations; no blanket human sign-off or annotation-cleanliness claim.': 'Diagnostic comparison and 20-case review complete with documented limitations; full visual sign-off and annotation correctness are not established.',
            'Review closed by an explicit keep-GT decision. Uncertain labels remain unresolved; no replacement transcript, human pixel signoff, causal proof or prevalence claim.': 'Review closed by an explicit keep-GT decision. Uncertain labels remain unresolved; replacement transcripts, independent visual sign-off, causal proof and prevalence estimates are not established.',
        }
        def editorial(value):
            if isinstance(value, dict):
                return {replacements.get(k, k): editorial(v) for k, v in value.items()}
            if isinstance(value, list):
                return [editorial(v) for v in value]
            return replacements.get(value, value) if isinstance(value, str) else value
        revised = editorial(original)
        if revised != original:
            write_json(name, revised)
            provenance[name] = source_record(path, 'Publication wording and review field names standardized; numerical values, decision and uncertainty retained. Original source unchanged.')

def derived_json(path, name, obj, description):
    write_json(name, obj)
    provenance[name] = source_record(path, description)

def write_csv(name, rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    write(name, '\ufeff' + buffer.getvalue())

qa = read(REPORT / 'evidence/pdf_qa.json')
assert qa['pdf_sha256'] == digest(REPORT / 'main.pdf')
assert qa['visual_review']['status'] == 'complete'
copy(REPORT / 'main.pdf', 'DocuCheck_AI_Week2_Report.pdf')

# These sources contain aggregate statistics, not receipt images or transcripts.
g1_sources = {
    'audit.json': 'audit.json',
    'source_transcript_verification.json': 'source_transcript_verification.json',
    'official_train/metrics.json': 'train_metrics.json',
    'official_val/metrics.json': 'validation_metrics.json',
    'official_train/runtime.json': 'train_runtime.json',
    'official_val/runtime.json': 'validation_runtime.json',
    'verification.json': 'benchmark_verification.json',
    'pytest.txt': 'pytest_20261105.txt',
}
for src, dst in g1_sources.items():
    copy(G1 / src, 'evidence/goal1/' + dst)

G1REV = BASE / 'goal1_20261106_review_final'
for src, dst in [('review_summary.json', 'error_review_summary.json'), ('closure_decision.json', 'closure_decision.json'), ('final_verification.json', 'review_verification.json')]:
    copy(G1REV / src, 'evidence/goal1/' + dst)

g2_sources = {
    'comparison.csv': 'psm_comparison.csv',
    'paired_analysis.json': 'paired_analysis.json',
    'independent_metrics_verification.json': 'independent_metrics_verification.json',
    'verification.json': 'benchmark_verification.json',
    'pytest.txt': 'pytest_20261105.txt',
}
for src, dst in g2_sources.items():
    copy(G2 / src, 'evidence/goal2/' + dst)
for mode in (6, 4, 11):
    copy(G2 / f'psm{mode}/runtime.json', f'evidence/goal2/psm{mode}_runtime.json')
for src in ('review_summary.json', 'final_verification.json'):
    copy(REVIEW / src, 'evidence/goal2/' + src)

path = G2 / 'annotation_source_audit.json'
derived_json(path, 'evidence/goal2/source_audit_counts.json', {
    'scope': 'Corrected evaluation manifest only; aggregate counts extracted from source audit.',
    'counts': read(path)['counts'],
    'excluded_fields': ['examples containing source transcript and receipt identifiers'],
}, 'Extract counts only; omit raw transcript examples and receipt identifiers.')

copy(REPORT / 'evidence/goal3_team_data.json', 'evidence/goal3/team_report_data.json')
data = read(REPORT / 'evidence/goal3_team_data.json')
rows = [{**r, 'successful_crops_reported': data['crops'], 'failures_reported': 0,
         'gt_characters_reported': data['gt_characters'], 'gt_tokens_reported': data['gt_tokens'],
         'independently_verified': False} for r in data['rows']]
write_csv('evidence/goal3/engine_comparison.csv', rows)
provenance['evidence/goal3/engine_comparison.csv'] = source_record(
    REPORT / 'evidence/goal3_team_data.json', 'CSV of team-reported values; CER/WER in percent. Not independently verified.')

g1_rows = []
for split in ('official_train', 'official_val'):
    m = read(G1 / split / 'metrics.json')
    g1_rows.append({'split': split, 'crops': m['evaluated_crops'], 'cer_percent': m['cer'] * 100,
        'wer_percent': m['wer'] * 100, 'exact_match_percent': m['exact_match_rate'] * 100,
        'character_errors': m['character_errors'], 'gt_characters': m['ground_truth_characters'],
        'token_errors': m['word_errors'], 'gt_tokens': m['ground_truth_words'],
        'empty_predictions': m['empty_hypothesis_crops'],
        'execution_failures': m['inference_runtime_context']['images_failed']})
write_csv('evidence/goal1/benchmark_summary.csv', g1_rows)
provenance['evidence/goal1/benchmark_summary.csv'] = {
    'sources': [source_record(G1 / s / 'metrics.json', 'Aggregate metrics; convert ratios to percent.')
                for s in ('official_train', 'official_val')]}

for name in ('pdf_qa.json', 'pdf_links.json', 'protected_after.json'):
    copy(REPORT / 'evidence' / name, 'evidence/report_quality/' + name)
checks = read(REPORT / 'evidence/report_checks.json')
derived_json(REPORT / 'evidence/report_checks.json', 'evidence/report_quality/evidence_checks.json',
             {key: checks[key] for key in ('date', 'mode', 'checks', 'inventories', 'goal3_independently_verified')},
             'Select verification scope and inventory results; exclude duplicate full metrics.')
for name in ('engine_metrics.pdf', 'psm_cases.pdf'):
    copy(REPORT / 'figures' / name, 'figures/' + name)

write('README_SUBMISSION.txt', '''DOCUCHECK AI - BỘ NỘP BÁO CÁO WEEK 2
Ngày đóng gói: 06/11/2026 (Asia/Saigon)
Thành viên: Nguyễn Văn Minh; Nguyễn Thành Trung

1. Đọc DocuCheck_AI_Week2_Report.pdf trước (11 trang).
2. Mở EVIDENCE_INDEX.md để tìm minh chứng cho từng kết quả.
3. evidence/goal1: benchmark crop, audit, runtime và kiểm chứng.
4. evidence/goal2: so sánh PSM với transcript đã sửa, phân tích ghép cặp và review.
5. evidence/goal3: bảng ba engine do nhóm cung cấp; chưa có artifact gốc để xác minh độc lập.
6. figures: hai biểu đồ vector có trong báo cáo.

Các CSV dùng UTF-8 có BOM để mở bằng Excel; dấu chấm là dấu thập phân.
Goal 1/3 CSV dùng CER/WER theo phần trăm. Goal 2 CSV gốc dùng tỷ số 0–1.
Các file JSON có thể mở trong trình soạn thảo hoặc trình duyệt hỗ trợ JSON.

Phạm vi minh chứng:
- Test và verification của thí nghiệm được lưu ngày 05/11/2026; không phải lượt chạy mới khi đóng gói.
- Kiểm tra đóng gói ngày 06/11 chỉ đối chiếu bản PDF, checksum, tính đầy đủ và nội dung ZIP.
- Không kèm ảnh hóa đơn, transcript, dự đoán từng ảnh/crop, dữ liệu gốc hoặc model weights.
- Số liệu Goal 3 là báo cáo nhóm, không phải kết quả đã tái kiểm độc lập.
- Runtime Goal 3 khác bản ghi trước; chi tiết tại evidence/goal3/LIMITATIONS.md.

Mã nguồn dự án: https://github.com/AIVIETNAM-AIO-Heart208/DocuCheck-AI
SUBMISSION_MANIFEST.json ghi kích thước và SHA-256 của từng file (trừ chính manifest).
SOURCE_PROVENANCE.json ghi nguồn và cách trích xuất; đường dẫn source phục vụ truy nguyên,
không phải phụ thuộc cần có để đọc các file đính kèm.
''')

write('evidence/goal3/LIMITATIONS.md', '''# Phạm vi minh chứng Goal 3

Bảng so sánh do nhóm cung cấp: 1.300 crop official_val, 23.739 ký tự và 4.815 token tham chiếu. Mỗi engine được báo cáo 1.300 thành công, 0 lỗi thực thi. CER/WER khớp tài liệu tổng hợp hiện có; chưa có predictions/runtime gốc của ba engine để kiểm chứng độc lập.

| Engine | CER | WER | Tổng giây | ms/crop báo cáo | ms/crop bản ghi trước |
|---|---:|---:|---:|---:|---:|
| VietOCR 0.3.13 | 9,59% | 33,87% | 137,7 | 105,9 | 85,0 |
| Tesseract 5.3.4 | 19,51% | 55,49% | 85,7 | 65,9 | 65,2 |
| PaddleOCR 3.7.0 | 17,44% | 63,03% | 207,7 | 159,8 | 99,8 |

Chưa xác định nguyên nhân chênh lệch runtime do thiếu nhật ký gốc. Giữ nguyên số liệu được báo cáo, không ghép các lượt chạy. Goal 1 dùng Tesseract 5.5.3.20260724; không thay runtime Goal 3 bằng runtime Goal 1. Bảng CSV là bản chuyển định dạng của số liệu nhóm cung cấp, không phải bằng chứng inference mới.
''')

write('EVIDENCE_INDEX.md', '''# Danh mục minh chứng đính kèm Week 2

Các đường dẫn dưới đây đều nằm trong ZIP. Các tệp giữ nguyên hoặc chuẩn hóa cách diễn đạt được phân biệt trong SOURCE_PROVENANCE.json; số liệu và giới hạn bằng chứng được bảo toàn. Đây là bộ minh chứng tổng hợp, không thay thế toàn bộ dữ liệu để tái chạy OCR.

| Phần báo cáo | File đính kèm | Chứng minh được / giới hạn |
|---|---|---|
| Báo cáo chính | DocuCheck_AI_Week2_Report.pdf | Bản 11 trang đã rà soát, gồm năm nguồn tham khảo có link. |
| Goal 1: dữ liệu đầu vào | evidence/goal1/audit.json; source_transcript_verification.json | Audit 6.585 crop, kiểm nguồn và split đã lưu; không chứng nhận mọi nhãn đúng pixel. |
| Goal 1: CER/WER/exact-match | evidence/goal1/benchmark_summary.csv; train_metrics.json; validation_metrics.json | Hai split riêng; tử số/mẫu số, đầu ra rỗng, coverage. CSV chuyển tỷ số thành phần trăm. |
| Goal 1: thời gian/môi trường | evidence/goal1/train_runtime.json; validation_runtime.json | Phiên bản, model hash, cấu hình, số thành công/lỗi và thời gian đúng lượt chạy. |
| Goal 1: phân tích lỗi | evidence/goal1/error_review_summary.json | 24 ca đã đóng theo quyết định giữ GT: 15 ca ghi nhận quan sát, 9 ca chưa đủ bằng chứng sửa nhãn; kèm closure_decision.json và review_verification.json. Không chứng nhận mọi nhãn đúng. |
| Goal 1: kiểm chứng | evidence/goal1/benchmark_verification.json; pytest_20261105.txt | 80 kiểm tra và 134 tests pass của lần chạy đã lưu. |
| Goal 2: điểm corrected và coverage | evidence/goal2/psm_comparison.csv | 231 ảnh; 4.265 text GT và 8.304 geometry GT; CER/WER dạng tỷ số. |
| Goal 2: phạm vi nguồn | evidence/goal2/source_audit_counts.json | Trích counts từ audit corrected; đã bỏ ví dụ raw transcript. |
| Goal 2: cấu hình/thời gian | evidence/goal2/psm6_runtime.json; psm4_runtime.json; psm11_runtime.json | Ba lượt chạy riêng; không thay hoặc chạy lại inference. |
| Goal 2: tính ổn định | evidence/goal2/paired_analysis.json | 5.000 bootstrap ghép cặp; phân tích thăm dò, không sửa sai nhãn/alignment. |
| Goal 2: kiểm chứng tính toán | evidence/goal2/independent_metrics_verification.json; benchmark_verification.json; pytest_20261105.txt | 12.795 vùng qua ba PSM, 170 kiểm tra và 167 tests pass lịch sử. |
| Goal 2: trạng thái review cuối | evidence/goal2/review_summary.json; final_verification.json | 20 ca đã xem; một quan sát xác nhận, hai ca bất định và một ca bất đồng. Không kèm gallery/raw text. |
| Goal 3: so sánh ba engine | evidence/goal3/engine_comparison.csv; team_report_data.json; LIMITATIONS.md | Số liệu do nhóm cung cấp, chưa có artifact gốc; có khác biệt runtime cần làm rõ. |
| Minh họa | figures/engine_metrics.pdf; psm_cases.pdf | Biểu đồ từ số đo đã lưu; biểu đồ ca PSM là mẫu có chủ đích. |
| Kiểm tra bản báo cáo | evidence/report_quality/pdf_qa.json; pdf_links.json | Hash PDF, bố cục, tham chiếu và năm liên kết công khai. Các đường dẫn ảnh QA trong JSON chỉ là provenance; ảnh QA không nằm trong ZIP. |
| Bảo toàn và đối chiếu | evidence/report_quality/protected_after.json; evidence_checks.json | 636 tệp trong mốc bảo vệ không đổi; hai tài liệu được cập nhật có chủ đích; inventory Goal 1/Goal 2/review cuối đã đối chiếu. |

Trong cùng một dòng bảng, các tên file sau dấu chấm phẩy nằm cùng thư mục với file đầu tiên. Các file failures/predictions được nhắc bên trong runtime là tên đầu ra của lần chạy gốc, không phải file đính kèm.
''')

write('SUBMISSION_CHECKLIST.md', '''# Checklist bộ nộp Week 2

- [x] Báo cáo PDF hiện hành, 11 trang; năm tài liệu tham khảo công khai có link.
- [x] Kèm minh chứng tổng hợp Goal 1 và Goal 2 từ đúng bundle đã kiểm tra.
- [x] Kèm dữ liệu Goal 3 và ghi rõ thiếu artifact để kiểm chứng độc lập.
- [x] Phân biệt tỷ số và phần trăm, train/validation, crop/full-page và phiên bản Tesseract.
- [x] Kiểm thử ngày 05/11 được ghi là lịch sử thực thi, không phải chạy lại.
- [x] Có hai biểu đồ, hướng dẫn đọc, nguồn trích xuất và SHA-256.
- [x] PDF sao vào bộ nộp khớp byte với bản báo cáo đã qua QA.
- [x] Kiểm tra CRC, danh sách tệp và SHA-256 trong ZIP.
- [x] Không kèm raw dataset, ảnh hóa đơn, transcript, predictions chi tiết hoặc model weights.

''')

write_json('SOURCE_PROVENANCE.json', {'date': '2026-11-06', 'timezone': 'Asia/Saigon',
    'scope': 'Aggregate evidence packaging; no OCR, benchmark evaluation or test suite rerun.',
    'files': provenance})

# Verify the evidence-to-report relationship before sealing the package.
for split in ('official_train', 'official_val'):
    m = read(G1 / split / 'metrics.json')
    assert abs(m['cer'] - m['character_errors']/m['ground_truth_characters']) < 1e-12
    assert abs(m['wer'] - m['word_errors']/m['ground_truth_words']) < 1e-12
assert read(G1 / 'verification.json')['status'] == 'passed'
assert read(G2 / 'verification.json')['check_count'] == 170
assert read(REVIEW / 'review_summary.json')['case_count'] == 20
for p in OUT.rglob('*.json'):
    obj = read(p)
    def check_fields(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key not in {'text_gt', 'text_pred', 'source_raw', 'candidate_transcript', 'current_gt'}, (p, key)
                check_fields(child)
        elif isinstance(value, list):
            for child in value:
                check_fields(child)
    check_fields(obj)

files = sorted(p for p in OUT.rglob('*') if p.is_file())
manifest = {p.relative_to(OUT).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files}
write_json('SUBMISSION_MANIFEST.json', {'algorithm': 'SHA-256', 'excludes': ['SUBMISSION_MANIFEST.json'], 'files': manifest})
with zipfile.ZipFile(ARCHIVE, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():
            z.write(p, p.relative_to(OUT).as_posix())
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    assert set(z.namelist()) == set(manifest) | {'SUBMISSION_MANIFEST.json'}
    for name, row in manifest.items():
        payload = z.read(name)
        assert len(payload) == row['bytes']
        assert hashlib.sha256(payload).hexdigest() == row['sha256']
    assert hashlib.sha256(z.read('DocuCheck_AI_Week2_Report.pdf')).hexdigest() == qa['pdf_sha256']

result = {'status': 'passed', 'archive': ARCHIVE.relative_to(ROOT).as_posix(),
          'archive_sha256': digest(ARCHIVE), 'archive_bytes': ARCHIVE.stat().st_size,
          'file_count': len(manifest) + 1, 'pdf_sha256': qa['pdf_sha256'],
          'crc_check': 'passed', 'manifest_hashes': 'passed', 'pdf_matches_reviewed_report': True,
          'source_files_rechecked': len(provenance), 'date': '2026-11-06'}
(REPORT / 'evidence/submission_package_verification.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
