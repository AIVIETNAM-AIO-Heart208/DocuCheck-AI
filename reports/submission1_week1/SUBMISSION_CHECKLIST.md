# Checklist Submission I — Module 05

Ngày kiểm tra: 28/10/2026 (Asia/Saigon). Dấu `[x]` là hạng mục đã có/đã làm theo phạm vi ghi rõ; `[ ]` là việc người nộp cần hoàn tất hoặc minh chứng chưa có.

**Kết luận kiểm tra cuối:** PDF đã hoàn thiện trong phạm vi báo cáo Week 1. Không còn placeholder, tham chiếu lỗi hoặc sai khác giữa source/PDF và checksum đã ghi. Bộ minh chứng chi tiết cần được đính kèm riêng nếu yêu cầu nộp bao gồm artifact và notebook; các giới hạn nghiên cứu bên dưới đã được công bố, không đặt thêm tiêu chí nghiệm thu ngoài ba goal.

## Báo cáo và phạm vi

- [x] Có `main.tex` tiếng Việt Unicode, source đầy đủ và bibliography thực sự được tham khảo.
- [x] Có PDF được biên dịch bằng XeLaTeX; kết quả QA cuối ghi trong `evidence/pdf_qa.json`.
- [x] Bao phủ Goal 1 — hiểu dữ liệu, EDA, audit annotation, duplicate/leakage.
- [x] Bao phủ Goal 2 — schema 1.1, provenance, split/policy, validation, tái lập và giới hạn rollback.
- [x] Bao phủ Goal 3 — Tesseract baseline, alignment, CER/WER, phân tích lỗi và giới hạn protocol.
- [x] Có bìa, tóm tắt, mục lục tự động, bảng/hình/công thức đánh số, tài liệu tham khảo và phụ lục minh chứng.
- [x] Phần nội dung chính đạt mục tiêu 10–15 trang; không thêm kế hoạch sản phẩm hoặc chức năng ngoài Week 1.
- [x] Không xem inference thành công là KIE thành công; không có claim field-level F1/accuracy hoặc detection F1 không phù hợp.
- [x] Mẫu review 40 ảnh được mô tả là mẫu tìm lỗi, không suy ra tỷ lệ lỗi toàn dataset.

## Chứng cứ và kiểm chứng

- [x] `EVIDENCE_INDEX.md` và phụ lục PDF ánh xạ claim lớn đến mã/hàm/config/artifact.
- [x] Đã rà soát lại ba goal với implementation và artifact; kết quả trong `EDITORIAL_REVIEW.md` và `evidence/goal_alignment_review.json`. Bản tinh gọn giữ 13 trang nội dung chính, bỏ biểu đồ KIE trùng bảng và các đoạn giải thích lặp.
- [x] Các đường dẫn notebook/code được tham chiếu tồn tại; trạng thái tracked/local và SHA-256 ghi trong `evidence/artifact_manifest.csv`.
- [x] 8.131 ảnh được giải mã, so kích thước/hash; 6.585 vùng KIE giữ nhãn/text/tọa độ nguồn; structural validation đạt, vẫn nêu 115 receipt geometry findings.
- [x] Counts split 904/231/20/391 được tái đếm; exact leakage trên active receipt/crop splits bằng 0, không suy không có near-duplicate leakage.
- [x] Hai bundle hardening A/B verify thành công và bốn artifact bằng byte; không claim đã chạy lại preparation.
- [x] Bundle `data/processed` cũ thiếu checksum metadata được nêu rõ; không sửa hoặc thay thế bundle.
- [x] OCR current artifact được phân biệt với lịch sử 5.3.4; metric hiện tại tái tính khớp toàn bộ summary/per-image/per-region, không claim inference mới.
- [x] 106 tests thực thi local có log; số 24/60/104 lịch sử được giữ đúng bối cảnh, không cộng dồn hoặc chọn số lớn nhất làm CI.
- [x] Output lưu sẵn bốn notebook được đọc/kiểm cú pháp; không claim chạy lại notebook.
- [x] Những số chưa độc lập xác minh được gắn lịch sử/chưa xác minh; không tạo ảnh, transcript, thí nghiệm hoặc kết quả giả thay thế.
- [x] Trạng thái CI được ghi **chưa xác minh**, vì connector trả status rỗng và chưa có successful run log.

## Tệp đi kèm và thông tin cần hoàn tất

- [x] Report directory có đủ LaTeX, hai figure PDF (EDA và lỗi OCR), hai sơ đồ TikZ, build script/instructions, evidence summary/manifest/log, checklist/index để đọc và biên dịch không cần raw dataset.
- [x] Các private outputs cần cho review sâu đã liệt kê cụ thể trong `EVIDENCE_INDEX.md`.
- [x] Đơn vị đào tạo **AI-VIETNAM** và khóa học **AIO2026** đã được người dùng xác nhận và điền trên bìa.
- [x] Đã điền tên nhóm **Winner Winner Chicken Dinner**, thành viên **Nguyễn Văn Minh** và **Nguyễn Thành Trung** theo thông tin người dùng cung cấp; bỏ mã học viên và giảng viên theo yêu cầu.
- [ ] Cung cấp repository ở commit đã ghi và **snapshot notebook local đúng hash** nếu người chấm yêu cầu; notebook có edits từ trước, chưa tự đóng gói hoặc commit.
- [ ] Đính kèm qua kênh được phép các manifest và bundle A/B, review CSV/sample, near-duplicate artifacts và OCR prediction/runtime/evaluation nếu yêu cầu nộp minh chứng chi tiết. Chúng đang có local nhưng chưa được tự sao chép vào bộ report công khai.
- [ ] Xác nhận quyền phân phối trước khi gửi artifact có transcript/ghi chú riêng tư hoặc dataset. Không gửi toàn bộ raw dataset mặc định.

## Giới hạn nghiên cứu và minh chứng đã công bố

- Chưa có snapshot prediction/runtime lịch sử Tesseract 5.3.4 để tái tính độc lập các số 29.849 boxes/CER 1,8965/WER 2,1795.
- Chưa có minh chứng successful CI check-run/log cho commit hiện tại; báo cáo chỉ xác nhận lần chạy tests local có log.
- Chưa có quyết định danh tính giao dịch cho 36 near-duplicate candidates; báo cáo không khẳng định hết leakage gần trùng.
- Chưa có liên kết parent receipt/KIE xác minh cho recognition crops; báo cáo giữ riêng hai nguồn.
- Chưa có taxonomy nguyên nhân OCR do người review gán nhãn hoặc field-level KIE; báo cáo đánh giá baseline và phân tích lỗi bước đầu đúng phạm vi Goal 3.

## Bảo toàn workspace

- [x] Không sửa mã chức năng, dữ liệu raw, annotation hoặc split; không huấn luyện/đổi model, không tải thêm model.
- [x] Không ghi đè bốn notebook có chỉnh sửa sẵn; không đưa receipt image/transcript vào PDF.
- [x] Chỉ tạo/cập nhật tệp phục vụ báo cáo dưới `reports/submission1_week1/`; không commit, push, publish hoặc gửi người khác.
