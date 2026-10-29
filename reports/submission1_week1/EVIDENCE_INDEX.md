# Hồ sơ minh chứng riêng — Submission I, Week 1

Cập nhật 29/10/2026, Asia/Saigon. PDF hiện tại có 9 trang, gồm bìa. Hồ sơ này phục vụ kiểm tra/nộp bài, không chèn vào PDF; người đọc báo cáo không cần mở repository.

## Phiên bản và phạm vi

Bản 19 trang là lịch sử. Bản 5 trang ở commit `cb04621065469cd0790aa05bb0b79a65a8bd8ba4` được bổ sung thành bản 8 trang tại commit `abc2f28`, rồi thành bản 9 trang tại commit `461f544ddb16bf5529c17a63e9a6fbd5bda87706`. PDF bộ nộp đã được đối chiếu byte với PDF ở commit này; mã nguồn được cung cấp bằng link GitHub cố định.

Bộ nộp final đã chuẩn bị tại `outputs/submission/DocuCheck_AI_Week1_FINAL.zip`, gồm PDF, tám tệp minh chứng tổng hợp, bốn ảnh xuất từ output notebook đã lưu kèm hồ sơ nguồn, checklist và hướng dẫn. Không kèm source.zip hoặc dữ liệu biên lai gốc. Danh sách tệp và hash nằm trong `SUBMISSION_MANIFEST.json` bên trong ZIP; việc upload do người dùng thực hiện.

Hai bộ A/B được kiểm tra lại bằng verifier ở chế độ chỉ đọc; đối chiếu đủ bốn thành phần đều giống hệt từng byte. Tử số/mẫu số CER 92.591/49.449 và WER 18.332/8.547 khớp metrics đã lưu. Các công thức trong PDF tổng hợp theo vùng hợp lệ, dùng dấu cách mảnh cho hàng nghìn và dấu phẩy cho thập phân. Không chạy lại preparation hoặc evaluation để có các kết quả này.

`evidence/verified_summary.json`, `goal_alignment_review.json` và `repository_context.json` giữ ngữ cảnh kiểm chứng thực nghiệm ngày 28/10. Chúng không xác định số trang hoặc trạng thái biên dịch hiện tại. `evidence/pdf_qa.json` và `final_review.json` áp dụng cho PDF hiện tại.

79 nguồn/artifact được đối chiếu SHA-256 với `evidence/artifact_manifest.csv`. Không chạy lại preparation, inference, evaluation, notebook, pytest hoặc rà soát pixel trong lượt hoàn thiện này. Đọc nhận xét đã lưu và kiểm tra số liệu không được trình bày như thí nghiệm mới.

Các đường dẫn tính từ gốc repo, trừ `evidence/` và `figures/` tính từ thư mục báo cáo.

## Đối chiếu các kết quả chính

| Nội dung | Nguồn đối chiếu | Kết quả và giới hạn |
|---|---|---|
| Quy mô và nguồn dữ liệu | `data/processed/manifest.jsonl`, `recognition_manifest.jsonl`; `docs/WEEK1_REPORT.md` | 1.546 receipt, 1.491 nội dung duy nhất; 1.155 train, 391 official; 6.585 vùng KIE, 40.868 vùng OCR và 6.585 crop riêng. Không suy liên kết parent receipt/KIE từ số crop. |
| Bảng bốn trường | Receipt manifest; `evidence/verified_summary.json` | Đếm lại trực tiếp theo canonical field. Tên nơi bán: 1.171/1.071/84; địa chỉ: 1.952/1.077/78; thời điểm: 1.347/1.088/67; tổng tiền: 2.114/1.081/74 (vùng/ảnh có nhãn/ảnh chưa có nhãn). Một nhãn chưa ánh xạ giữ riêng. |
| EDA | Verified summary, notebook 02, `figures/eda_distributions.pdf` | Đặc trưng thật của 1.155 ảnh đã được tính trong lượt kiểm chứng gốc. Các đại lượng là thống kê độc lập, không phải điểm chất lượng OCR. |
| Rà soát nhãn và ba tình huống | `outputs/audit/week1/annotation_review.csv`; `docs/WEEK1_REPORT.md`, phần phân loại lỗi | 40 reviewed: 6 correct, 32 incorrect, 2 uncertain. Các tình huống sai trường, vùng bao thiếu tên và sai giá trị dựa trên nhận xét đã xác nhận; không đưa mã ảnh hoặc text vào PDF, không review lại pixel. |
| Hình học | Receipt manifest; verified summary | 6 ảnh có vùng KIE tự giao, 109 ảnh khác có transcript vượt biên; tổng 115. Phân biệt với vùng sai phạm vi phát hiện trực quan. |
| Trùng và chia tập | `src/docucheck/data/splitting.py`; split summary; `outputs/audit/week1/near_duplicate_summary.json` | 904 train, 231 dev, 20 cách ly, 391 official. Seed 42, dev theo 20% số nhóm. Zero trùng chính xác qua split hoạt động; 36 ứng viên gần trùng chưa phân xử, không tái băm lần này. |
| Chuẩn hóa và kiểm tra | `docs/DATA_SCHEMA.md`; mã data; `scripts/prepare_dataset.py` | Giữ raw/provenance, trạng thái thiếu/rỗng/lỗi. 8.131 ảnh được giải mã, đối chiếu kích thước/hash trong lượt kiểm chứng gốc. Cấu trúc hợp lệ không chứng nhận nhãn đúng nội dung. |
| Tái lập | `outputs/audit/goal2_hardening_20261028/run_a/`, `run_b/`, `verification.json` | Hai bộ qua verifier, bốn tệp giống hệt byte. `data/processed` cũ thiếu checksum metadata: không chọn làm bộ đã qua verifier mới; không trộn các bộ. |
| OCR và runtime | `outputs/ocr/tesseract_internal_dev/runtime.json`, predictions/failures; mã OCR | Tesseract 5.5.3.20260724, CPU, tiếng Việt, PSM 6/OEM 1; 231 success, 0 failure, 26.859 boxes. Không inference lại. |
| CER/WER và phân tích | `outputs/ocr/evaluation/metrics.json`, per-image/per-region; mã evaluation | CER 92.591/49.449; WER 18.332/8.547; 8.304 vùng dùng, 104 loại; 1.886 unmatched, 10.488 unassigned. Đã tái tính khớp trong lượt kiểm chứng gốc; lần này đối chiếu số liệu/hash. 10.488/26.859 xấp xỉ 39%, không phải tỷ lệ nhận thừa. |
| Biểu đồ OCR | Per-image metrics; `figures/ocr_error_distribution.pdf` | Vẽ lại từ 231 dòng đã lưu, cùng 25 bins, chỉ đổi nhãn trục sang tiếng Việt. Không tính lại metric hoặc inference. |
| Tests local | `evidence/pytest.txt` | 106 passed in 1.90s, Python 3.12.16/Windows, lần chạy gốc; khác log CI. |
| CI | `evidence/ci_status.json`; GitHub Actions | 106 passed in 1.89s tại commit cb04621; run 40857742742, job 123392875419. Không chứng minh annotation hoặc thí nghiệm dữ liệu thật đúng. |
| PDF | `evidence/pdf_qa.json`, `final_review.json`, `latex-final.log` | 9 trang; kiểm tra tham chiếu bảng/công thức, glyph, font, tràn, tọa độ chữ và xem bản render. PDF không chứa tên file/đường dẫn nội bộ. |

## Bộ minh chứng tối thiểu cho việc nộp

1. Báo cáo: `main.pdf`; nếu cần nguồn biên dịch, kèm `main.tex`, hai hình trong `figures/` và `BUILD.md`.
2. Tổng hợp: `evidence/verified_summary.json`, `goal_alignment_review.json`, `ci_status.json`, `pytest.txt`, `pdf_qa.json`, `final_review.json`, `artifact_manifest.csv`, `submission_manifest.csv` và hồ sơ này. Các số liệu tổng hợp giúp theo dõi kết quả; không thay thế bằng chứng gốc khi cần kiểm chứng sâu.
3. Mã/notebook: repository đúng commit và snapshot thay đổi cục bộ được chọn cho lần nộp. Bốn notebook local có output, còn commit cb04621 đã xóa output. Không coi notebook source là bằng chứng đã chạy; dùng đúng snapshot nếu cần cung cấp đầu ra.
4. Nếu yêu cầu kiểm chứng sâu: cung cấp có kiểm soát các bundle A/B, validation/split, review, runtime, metrics, prediction và alignment cần thiết. Kiểm tra transcript, ghi chú và ảnh trước khi chia sẻ. Mã ảnh/hash không bảo đảm ẩn danh.

Chưa tự tạo ZIP, đăng tải outputs hoặc gửi dữ liệu gốc. Hướng dẫn tái lập chỉ ra cách kiểm tra, không thay thế log hoặc kết quả gốc nếu quy định nộp đòi bằng chứng thực thi.

## Ngữ cảnh lịch sử và giới hạn

- Tài liệu/YAML cũ ghi Tesseract 5.3.4, 29.849 boxes, CER 1,8965, WER 2,1795. Thiếu snapshot riêng; PDF hiện tại dùng bộ kết quả thực có 5.5.3.20260724. Không tuyên bố cải thiện giữa hai môi trường.
- Trạng thái CI ngày 28/10 chỉ có `statuses: []`, không chứng minh Actions thất bại. Run/log thành công đã được bổ sung vào `ci_status.json`; giữ phản hồi cũ trong trường lịch sử.
- Các phần 19/6 trang trong `EDITORIAL_REVIEW.md` được ghi nhãn lịch sử. QA hiện tại xác định số trang và hash của bản cuối.
- Còn 36 cặp nghi gần trùng chưa phân xử, nhãn chưa sửa toàn bộ, chưa có taxonomy nguyên nhân từng ca OCR và chưa có đánh giá KIE. Không tạo kết quả thay thế cho phần chưa có bằng chứng.
