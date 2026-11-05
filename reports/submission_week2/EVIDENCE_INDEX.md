# Hồ sơ minh chứng báo cáo Week 2

Ngày đối chiếu: 06/11/2026, Asia/Saigon. Đường dẫn bên dưới tính từ gốc repo. PDF là báo cáo dành cho giảng viên; hồ sơ này giữ chi tiết kỹ thuật và các điểm chưa xác minh.

## Phân loại nguồn

Nguồn công khai dưới đây bổ sung căn cứ phương pháp, không thay thế các artifact thực nghiệm A/B/C. Bản PDF hiện hành có 11 trang; tài liệu tham khảo chỉ giữ năm nguồn công khai có link. Hồ sơ nội bộ được truy nguyên trong bảng bên dưới, không liệt kê trong mục tham khảo của PDF.

## Nguồn tham khảo công khai đã kiểm tra ngày 06/11/2026

| Nguồn chính thức | Link trực tiếp | Phạm vi trích dẫn |
|---|---|---|
| Ban tổ chức MC-OCR, RIVF 2021 | https://www.rivf2021-mc-ocr.vietnlp.com/ | Tên dữ liệu, bối cảnh ảnh hóa đơn tiếng Việt; số crop cục bộ vẫn dẫn artifact. |
| Nhóm phát triển Tesseract | https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method | Định nghĩa PSM 4, 6, 7 và 11; không dẫn cho CER/WER hoặc tốc độ nhóm đo. |
| pbcquoc/VietOCR | https://github.com/pbcquoc/vietocr#model-zoo | Xác nhận cấu hình vgg_transformer trong kho gốc; không nhập điểm hay thời gian upstream vào benchmark nhóm. |
| PaddleOCR/PaddlePaddle | https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html | Mô-đun recognition và latin_PP-OCRv5_mobile_rec. Không dùng model card có đoạn giới thiệu nhầm ngôn ngữ để mô tả model. |
| Jitsi/JiWER | https://jitsi.github.io/jiwer/reference/process/ | CER/WER theo Levenshtein, cộng số lỗi và độ dài trước khi chia. Chỉ là nguồn đối chiếu định nghĩa; không khẳng định pipeline đã sử dụng JiWER. |

Đã đọc các trang để đối chiếu trực tiếp, không chỉ dựa vào kết quả tìm kiếm. Các tài liệu online có thể được cập nhật; ngày truy cập ghi trong PDF. `evidence/pdf_links.json` kiểm tra các URI được nhúng trong bản PDF, không thay thế bản kiểm tra nội dung nguồn.

## Phân loại bằng chứng thực nghiệm

- **A — Artifact đã đối chiếu:** đọc tệp hiện có, kiểm tra hash/inventory và tính nhất quán số tổng hợp. Không có inference mới; không tự nhận đây là đánh giá độc lập toàn bộ chuỗi từ pixel tới metrics.
- **B — Tài liệu tổng hợp:** dùng mô tả phương pháp, môi trường, lịch sử test và nhận xét đã lưu. Không biến thao tác review trước đó thành việc vừa thực hiện.
- **C — Nhóm cung cấp:** giữ nguyên báo cáo Goal 3 trong yêu cầu. Thiếu artifact để xác minh độc lập coverage, runtime và predictions.

## Ánh xạ kết luận

| Nội dung | Nguồn | Loại và đối chiếu |
|---|---|---|
| Bìa, tên nhóm/thành viên, phong cách | `reports/submission1_week1/main.tex`, `BUILD.md`, `EDITORIAL_REVIEW.md`, `SUBMISSION_CHECKLIST.md` | B. AI-VIETNAM/AIO2026; Nguyễn Văn Minh, Nguyễn Thành Trung. Chưa xác nhận số submission/module Week 2, nên bỏ hai trường này. |
| Phạm vi ba goal | `docs/WEEK2_REPORT.md`, `docs/PSM_COMPARISON_REPORT.md`, yêu cầu đính kèm | B/C. WEEK2_REPORT chỉ là Goal 1; GOAL3_OCR_BASELINE có nội dung lịch sử, không dùng tên tài liệu để gán scope. |
| Audit 6.585 crop, split, ID và trùng chính xác | `outputs/ocr/week2/goal1_20261105/audit.json`; `source_transcript_verification.json` | A/B. Đọc audit và kiểm hash tệp; không giải mã hoặc băm lại toàn bộ ảnh raw trong lượt viết báo cáo. Audit khẳng định giữ đúng nguồn, không xác nhận annotation đúng pixel. |
| CER/WER/exact-match Goal 1, tử số/mẫu số | `outputs/ocr/week2/goal1_20261105/{official_train,official_val}/metrics.json`, `per_crop_metrics.jsonl` | A. Cộng lại lỗi và độ dài đã lưu; đối chiếu số dòng, exact-match ratio, manifest/prediction/runtime hashes. Không tính lại edit distance từ chuỗi. |
| Thời gian Goal 1 | Các `runtime.json`, metrics; `docs/WEEK2_REPORT.md`, protocol | A/B. 530,07/129,16 giây; 100,24/99,30 ms. Chi phí gồm subprocess, kiểm ảnh, TSV; chưa cô lập tải máy. |
| 24 mẫu lỗi và 10/7/1/3/3 nhóm nhận định | `outputs/ocr/week2/goal1_20261105/error_review/review_cases.json`, `review_summary.json` | A/B. Đếm nhóm khớp summary. Review lịch sử, không xem lại pixel hay gán tác giả review. Trạng thái phân xử vẫn chờ xác nhận. |
| Goal 1: 134 tests, 80 checks | `outputs/ocr/week2/goal1_20261105/pytest.txt`, `verification.json`; `docs/WEEK2_REPORT.md` | A/B. Là lịch sử thực thi ngày 05/11, không phải suite chạy ngày 06/11. |
| Parser và 8.408/104/4.265/4.039 vùng | `docs/PSM_CORRECTED_PROTOCOL.md`; `outputs/ocr/week2/goal2_20261105_corrected/annotation_source_audit.json` | A/B. Sửa text GT không sửa predictions; manifest gốc giữ nguyên. Không dùng CER/WER sai GT để tính cải thiện. |
| Bảng corrected, hai phạm vi coverage | `outputs/ocr/week2/goal2_20261105_corrected/comparison.csv`, `psm*/metrics.json` | A. Mẫu số 56.619 ký tự/11.584 token; kiểm tỷ số trong bảng. Text scope 4.265; geometry scope 8.304. |
| Chênh lệch PSM 11 và bootstrap | `outputs/ocr/week2/goal2_20261105_corrected/paired_analysis.json` | A. 110 tốt/108 kém/13 bằng theo CER; nhân chênh lệch và CI với 100 để ra điểm phần trăm. 5.000 bootstrap, seed 42, giả định ảnh độc lập. |
| Review 20 ca; ca 05/10/16/17 | `outputs/ocr/week2/goal2_20261105_review_final/review_cases.json`, `review_summary.json`, `user_feedback.json`, `focused_trace.json` | A/B. Chỉ ca 05 có quan sát người dùng xác nhận; 10/16 bất định, 17 bất đồng. Đọc review đã lưu, không tự nhận review pixel mới. |
| Hình CER ba ca PSM | `review_cases.json` của review cuối, ca 01/05/07 | A. Vẽ từ trường `measurements[psm].cer`; mã ca giúp tra hồ sơ, không đưa ID hóa đơn hoặc transcript vào PDF. Không phải ảnh OCR sinh giả. |
| Goal 2: 167 tests/170 checks/12.795 vùng kiểm độc lập | `docs/PSM_COMPARISON_REPORT.md`; bundle `pytest.txt`, `verification.json`, `independent_metrics_verification.json` | A/B. Lịch sử thực thi; lượt báo cáo chỉ kiểm inventory và số liệu, không chạy lại verifier/evaluator hoặc test suite. |
| Ba engine: CER/WER, model, runtime | Báo cáo nhóm trong yêu cầu; `docs/GOAL3_OCR_BASELINE.md` | C/B. CER/WER trong tài liệu khớp bảng nhóm. `outputs/ocr/engine_comparison/` và các bundle engine được dẫn không có trong workspace. Không tuyên bố đã kiểm ID/predictions của Goal 3. |
| Hình CER/WER Goal 3 | `reports/submission_week2/evidence/goal3_team_data.json` | C. Vẽ đúng bảng nhóm, mỗi chỉ số một thang đo. Tỷ lệ giảm tương đối tính trên các phần trăm được cung cấp, có làm tròn. |

## Chênh lệch runtime Goal 3 chưa giải quyết

| Engine | Nhóm cung cấp (ms/crop) | Tài liệu lịch sử (ms/crop) |
|---|---:|---:|
| VietOCR | 105,9 | 85,0 |
| Tesseract | 65,9 | 65,2 |
| PaddleOCR | 159,8 | 99,8 |

Tài liệu lịch sử ghi các lượt cuối tuần tự trên CPU sau vấn đề oversubscription của lượt song song, nhưng không có bundle tại chỗ để đối chiếu run ID/timer. Không thể xác định chênh lệch do định nghĩa thời gian hay khác lượt chạy. Bảng chính dùng nguyên 137,7/85,7/207,7 giây và 105,9/65,9/159,8 ms do nhóm cung cấp. Không lấy thời gian từ Goal 1 (Tesseract 5.5.3) ghép vào Goal 3 (5.3.4). Các tổng và trung bình công bố có làm tròn; không suy số thập phân chính xác hoặc ép chúng bằng nhau tuyệt đối.

## Hồ sơ kiểm chứng mới của báo cáo

- `evidence/report_checks.json`: số liệu đọc từ artifact, cộng lỗi đã lưu và kết quả kiểm inventory. Không inference/evaluation mới.
- `evidence/source_hashes.json`: SHA-256 của nguồn nội dung chính.
- `evidence/protected_before.json`: mốc toàn bộ tệp ở Week 1, các bundle Week 2, docs/src/tests và hai manifest để kiểm không thay đổi.
- `evidence/protected_after.json`: kết quả so với mốc sau khi hoàn tất.
- `evidence/pdf_qa.json`: metadata, số trang, kiểm bố cục/text tự động và trạng thái xem PNG.
- `qa/`: log build, ảnh render của bản cuối và text được trích xuất.

Hai biểu đồ trong PDF chỉ dùng số đo tổng hợp hoặc metric của các ca đã lưu. Không đưa ảnh hóa đơn/transcript raw vào PDF do điều kiện chia sẻ nguồn chưa được xác minh; các minh họa định lượng và diễn giải dựa trên review thật. Không tạo lại gallery, sửa nhãn hoặc làm mới benchmark.
