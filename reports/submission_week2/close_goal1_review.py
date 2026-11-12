"""Record the approved keep-GT disposition without rewriting sealed evidence."""
from pathlib import Path
import collections
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'outputs/ocr/week2/goal1_20261105/error_review'
OUT = ROOT / 'outputs/ocr/week2/goal1_20261106_review_final'
OUT.mkdir(exist_ok=True)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
rows = json.loads((OLD/'review_cases.json').read_text(encoding='utf-8'))
notes = [
    'Crop nhiều dòng, đầu ra rỗng; thấy Khu nha o trong ảnh nhưng GT thiếu Khu. Chưa thử PSM khác để xác lập nguyên nhân.',
    'Chữ nhạt và mờ; đầu ra rỗng. Không xác nhận được từng ký tự nguồn.',
    'Chữ in chấm, đầu ra rỗng; dấu địa danh chưa đủ rõ để xác nhận toàn bộ GT.',
    'Crop hai dòng, đầu ra rỗng; ký tự trước dat trong nguồn khác chữ nhìn thấy. Giữ GT để bảo toàn phép đo.',
    'Có khác biệt dấu ở tên cửa hàng; không xác nhận transcript thay thế từ crop này.',
    'OCR khác dấu ở Chợ; phần chữ nhỏ làm giảm độ chắc chắn của nhận định nguyên nhân.',
    'Có nghi vấn cổ/CÔ trong nguồn; không xác nhận nhãn thay thế.',
    'Ngày bán và thời gian đọc được; OCR khác dấu ở Ngày.',
    'Chuỗi ngày giờ giữ nguyên ký tự chính; khác khoảng trắng quanh dấu phân cách.',
    'Thời gian giữ nguyên chữ số; khác khoảng trắng sau dấu hai chấm.',
    'Ngày giờ giữ nguyên chữ số; khác vị trí khoảng trắng quanh dấu phân cách.',
    'Ngày giờ giữ nguyên chữ số; khác khoảng trắng quanh dấu phân cách.',
    'Tháng nhìn gần 08 nhưng GT là 09 và OCR là 06; chưa đủ chắc để thay nhãn. OCR còn sai dấu phân cách.',
    'Chữ số ngày giờ khớp; OCR thiếu dấu hai chấm trước phút và khác khoảng trắng.',
    'Chuỗi số tiền khớp; tiền tố VND/UND khác ký tự đầu. Không suy ra lỗi giá trị tiền.',
    'Ảnh thể hiện 12:33:53; GT thiếu một dấu hai chấm, OCR thiếu hai dấu và sai chữ số cuối.',
    'Crop rất nhỏ, OCR mất nhiều ký tự; không xác nhận từng nét chữ của nhãn nguồn.',
    'Tiêu đề địa chỉ đại lý đọc được ở mức từ; OCR sai nhiều ký tự và dấu.',
    'Ngày tháng bị nhòe mạnh; không xác nhận tháng của nhãn nguồn.',
    'Thời gian nhìn thấy, OCR sai nhiều ký tự; GT có khoảng trắng quanh dấu hai chấm.',
    'Địa chỉ đọc được ở mức từ; OCR sai nhiều chữ và dấu, chưa tách được ảnh hưởng riêng của độ mờ.',
    'Ảnh có vẻ là PHẢ thay vì HÀ; dấu và nét mờ nên không xác nhận transcript thay thế.',
    'Logo VinCommerce nghiêng/cách điệu; OCR sai nhiều ký tự. Không có thí nghiệm xác lập tác động riêng của font.',
    'Có dấu phân cách nhìn thấy nhưng nguồn dùng khoảng trắng; phần mã cuối chưa đủ rõ để chốt toàn bộ transcript.',
]
uncertain = {2,3,5,7,13,17,19,22,24}
for row, note in zip(rows, notes):
    n = row['case_number']
    row['historical_adjudication_status'] = row.pop('adjudication_status')
    row['adjudication_status'] = 'closed_keep_original_gt'
    row['final_observation'] = note
    row['label_disposition'] = 'insufficient_evidence_to_relabel' if n in uncertain else 'observation_recorded_no_relabeling'
    row['closure_date'] = '2026-11-06'
    row['local_image'] = '../goal1_20261105/error_review/' + row['local_image']
    row['crop_sha256'] = sha(OUT / row['local_image'])
save('review_cases.json', rows)
save('closure_decision.json', {
    'date':'2026-11-06', 'confirmation_source':'Explicit confirmation in project conversation',
    'confirmation_text':'Xác nhận: giữ GT, đóng review với giới hạn đã ghi',
    'scope':'Close 24-case review; retain original GT and benchmark; record uncertain labels as insufficient evidence.',
    'human_pixel_review_claimed':False, 'reviewer_identity':None,
    'all_labels_certified_correct':False, 'ground_truth_modified':False,
})
summary = json.loads((OLD/'review_summary.json').read_text(encoding='utf-8'))
summary.update(adjudication_status='closed_keep_original_gt', closure_date='2026-11-06',
    closure_confirmed=True, closed_cases=24, pending_cases=0,
    label_disposition_counts=dict(collections.Counter(r['label_disposition'] for r in rows)),
    label_uncertainty_case_numbers=sorted(uncertain),
    cause_counts_scope='Historical diagnostic categories retained; not confirmed causal or corrected-label counts.',
    limitations='Review closed by an explicit keep-GT decision. Uncertain labels remain unresolved; no replacement transcript, human pixel signoff, causal proof or prevalence claim.',
    source_review_sha256=sha(OLD/'review_cases.json'))
save('review_summary.json', summary)
assert len(rows)==24 and all(not r['ground_truth_modified'] for r in rows)
assert all((OUT/r['local_image']).exists() for r in rows)
assert sum(summary['label_disposition_counts'].values())==24
save('final_verification.json', {'status':'passed','cases':24,'closed_cases':24,'pending_cases':0,
    'label_uncertainty_cases':len(uncertain),'source_cases_sha256':sha(OLD/'review_cases.json'),
    'all_crop_hashes_recorded':True,'ground_truth_modified':False,'benchmark_rerun':False})
save('artifact_manifest.json', {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(summary, ensure_ascii=False, indent=2))
