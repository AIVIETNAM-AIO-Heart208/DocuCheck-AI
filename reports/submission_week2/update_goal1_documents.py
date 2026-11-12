"""Apply the confirmed Goal 1 closure to report and packaging consumers."""
from pathlib import Path
import hashlib
import json
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
def edit(path, old, new):
    text = path.read_text(encoding='utf-8')
    assert old in text, (path, old)
    path.write_text(text.replace(old,new),encoding='utf-8')
edit(HERE/'prepare_report.py', "REV = BASE / 'goal2_20261105_review_final'", "REV = BASE / 'goal2_20261105_review_final'\nG1REV = BASE / 'goal1_20261106_review_final'")
edit(HERE/'prepare_report.py', '(G1, G2, REV)', '(G1, G2, REV, G1REV)')
edit(HERE/'prepare_report.py', "G1 / 'error_review/review_cases.json'", "G1REV / 'review_cases.json'")
edit(HERE/'prepare_report.py', "G1 / 'error_review/review_summary.json'", "G1REV / 'review_summary.json'")
edit(HERE/'main.tex', 'Nghi transcript nguồn sai dấu, cần phân xử', 'Nghi transcript nguồn sai dấu, giữ GT')
edit(HERE/'main.tex', '\\note{\\textbf{Giới hạn của phân tích lỗi.} Cả 24 mẫu có nhận xét, mức tin cậy và bằng chứng đối chiếu. Các trường hợp chưa rõ nhãn nguồn cần được thẩm định trước khi hiệu chỉnh. Kết quả hiện tại phục vụ chẩn đoán; chưa xác lập nguyên nhân của mọi lỗi hoặc tạo ra một bộ nhãn đã được xác nhận đầy đủ.}', '\\note{\\textbf{Kết thúc rà soát ngày 06/11/2026.} Đã đóng review 24/24 mẫu theo quyết định giữ nguyên GT và điểm benchmark: 15 mẫu ghi nhận quan sát, 9 mẫu chưa đủ bằng chứng để sửa nhãn. Đây là kết luận xử lý của lượt rà soát, không chứng nhận mọi nhãn đúng hoặc xác lập nguyên nhân của mọi lỗi.}')
edit(ROOT/'docs/WEEK2_REPORT.md', 'mức tin cậy và đang chờ người xác nhận trước khi dùng để sửa nhãn.', 'mức tin cậy. Ngày 06/11/2026, nhóm xác nhận đóng review 24/24 ca theo quyết định giữ GT: 15 ca ghi nhận quan sát, 9 ca chưa đủ bằng chứng để sửa nhãn. Không còn ca chờ quyết định xử lý; bất định nhãn vẫn được giữ rõ, không chứng nhận mọi nhãn đúng. Hồ sơ cuối: `outputs/ocr/week2/goal1_20261106_review_final/`; hồ sơ ngày 05/11 được bảo toàn.')
edit(ROOT/'docs/WEEK2_REPORT.md', 'Nghi transcript nguồn sai dấu, cần phân xử', 'Nghi transcript nguồn sai dấu, giữ GT')
with (ROOT/'docs/WEEK2_HANDOFF.md').open('a',encoding='utf-8') as f:
    f.write('\n## Goal 1 review closure — 2026-11-06\n\nThe 24-case review is closed by an explicit keep-original-GT decision: 15 cases have recorded observations and 9 have insufficient evidence to relabel. This does not certify all source labels. Benchmark scores and the sealed 2026-11-05 bundle are unchanged. Current review: `outputs/ocr/week2/goal1_20261106_review_final/`; current submission: `outputs/submission/DocuCheck_AI_Week2_FINAL_v2.zip`.\n')
edit(HERE/'EVIDENCE_INDEX.md', 'Review lịch sử, không xem lại pixel hay gán tác giả review. Trạng thái phân xử vẫn chờ xác nhận.', 'Đã đối chiếu lại 24 crop; quyết định giữ GT được xác nhận ngày 06/11. Hồ sơ hiện hành: `outputs/ocr/week2/goal1_20261106_review_final/`. Đóng 24 ca: 15 ca ghi nhận quan sát, 9 ca chưa đủ bằng chứng sửa nhãn. Không chứng nhận mọi nhãn đúng; bảng nhóm nguyên nhân vẫn là chẩn đoán lịch sử.')
for name in ('EVIDENCE_INDEX.md','SUBMISSION_CHECKLIST.md','audit_submission_language.py','package_submission.py'):
    edit(HERE/name, 'DocuCheck_AI_Week2_FINAL', 'DocuCheck_AI_Week2_FINAL_v2')
edit(HERE/'EVIDENCE_INDEX.md', 'gồm 36 file, 297.619 byte', 'gồm 38 file (kích thước và SHA-256 tại `evidence/submission_package_verification.json`)')
edit(HERE/'SUBMISSION_CHECKLIST.md', 'gồm 36 file (~291 KiB)', 'gồm 38 file; kích thước và SHA-256 tại `evidence/submission_package_verification.json`')
for name in ('SUBMISSION_CHECKLIST.md','EVIDENCE_INDEX.md'):
    with (HERE/name).open('a',encoding='utf-8') as f:
        f.write('\nCập nhật Goal 1 ngày 06/11: đóng 24/24 ca theo quyết định giữ GT; 15 ca ghi nhận quan sát, 9 ca chưa đủ bằng chứng sửa nhãn. Hồ sơ ngày 05/11 và benchmark không đổi. Hai tài liệu docs/WEEK2_REPORT.md và docs/WEEK2_HANDOFF.md được cập nhật có chủ đích; các tệp khác trong mốc bảo vệ giữ nguyên. ZIP v2 thay thế bản FINAL cũ khi nộp.\n')
edit(HERE/'package_submission.py', "    'error_review/review_summary.json': 'error_review_summary.json',\n", '')
edit(HERE/'package_submission.py', 'g2_sources = {', "G1REV = BASE / 'goal1_20261106_review_final'\nfor src, dst in [('review_summary.json', 'error_review_summary.json'), ('closure_decision.json', 'closure_decision.json'), ('final_verification.json', 'review_verification.json')]:\n    copy(G1REV / src, 'evidence/goal1/' + dst)\n\ng2_sources = {")
edit(HERE/'package_submission.py', '24 mẫu và nhóm nhận định; chưa xác nhận nhãn toàn bộ, không ước lượng tỷ lệ lỗi quần thể.', '24 ca đã đóng theo quyết định giữ GT: 15 ca ghi nhận quan sát, 9 ca chưa đủ bằng chứng sửa nhãn; kèm closure_decision.json và review_verification.json. Không chứng nhận mọi nhãn đúng.')
edit(HERE/'package_submission.py', '638 tệp nguồn không đổi', '636 tệp trong mốc bảo vệ không đổi; hai tài liệu được cập nhật có chủ đích')
edit(HERE/'quality_check.py', 'assert not changed, changed', "authorized = json.loads((HERE / 'evidence/authorized_document_updates.json').read_text(encoding='utf-8'))\nassert set(changed) == set(authorized), changed\nassert all(sha(ROOT / p) == row['after_sha256'] and baseline[p] == row['before_sha256'] for p, row in authorized.items())\nsave('evidence/protected_after.json', {'date':'2026-11-06', 'files_checked':len(baseline), 'unchanged':len(baseline)-len(changed), 'authorized_document_updates':authorized, 'unexpected_changes':[]})")
edit(HERE/'quality_check.py', "'protected_files_unchanged': len(baseline)", "'protected_files_unchanged': len(baseline)-len(changed)")
baseline = json.loads((HERE/'evidence/protected_before.json').read_text(encoding='utf-8'))
updates = {p:{'before_sha256':baseline[p], 'after_sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest(), 'reason':'User-authorized Goal 1 closure documentation; original experimental evidence unchanged.'} for p in ['docs/WEEK2_REPORT.md','docs/WEEK2_HANDOFF.md']}
(HERE/'evidence/authorized_document_updates.json').write_text(json.dumps(updates,indent=2)+'\n',encoding='utf-8')
with (HERE/'EDITORIAL_REVIEW.md').open('a',encoding='utf-8') as f:
    f.write('\n## Goal 1, 06/11/2026\n\nĐã đối chiếu lại đủ 24 crop và ghi quyết định giữ GT được xác nhận. 15 ca ghi nhận quan sát; 9 ca chưa đủ bằng chứng sửa nhãn. Đóng review không đồng nghĩa xác nhận toàn bộ nhãn. Báo cáo và gói v2 dùng hồ sơ mới, không sửa bundle gốc.\n')
