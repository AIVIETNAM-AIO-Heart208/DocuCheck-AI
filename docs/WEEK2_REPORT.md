# Week 2 — Kết quả Goal 1: Clean OCR Benchmark

**Ngày chạy:** 05/11/2026, Asia/Saigon.

**Trạng thái:** Hoàn thành Goal 1 về kỹ thuật: audit, inference, CER/WER/exact-match,
tests, phân tích trực quan 24 mẫu và bộ minh chứng tái lập. Các nhận xét có ghi
mức tin cậy và đang chờ người xác nhận trước khi dùng để sửa nhãn.

**Phạm vi báo cáo:** Goal 1. Báo cáo này không nghiệm thu Goal 2/3 của Week 2.

## 1. Kết quả chính

Tesseract `vie`, OEM 1, **PSM 7**, ảnh crop gốc, CPU, một worker/batch size 1.
Ghép các từ theo thứ tự TSV rồi so trực tiếp với transcript, không ghép polygon.

| Split | Vai trò | Crop đánh giá | Micro CER | Micro WER | Exact-match | Prediction rỗng | Lỗi thực thi |
|---|---|---:|---:|---:|---:|---:|---:|
| `official_train` | Diagnostic | 5.285 | **20,1183%** | **56,2225%** | **22,6868%** | 54 | 0 |
| `official_val` | Benchmark cấu hình cố định | 1.300 | **20,6496%** | **56,1786%** | **23,6923%** | 18 | 0 |

Coverage đánh giá và coverage prediction hợp lệ đều **100%** ở cả hai split;
không loại mẫu nào. Prediction rỗng là inference thành công nhưng không có từ,
được tính là lỗi xóa toàn bộ GT, khác với lỗi thực thi. Không gộp điểm hai split.

| Thành phần kiểm chứng | Train | Validation |
|---|---:|---:|
| Lỗi ký tự / tổng ký tự GT chuẩn hóa | 19.788 / 98.358 | 4.902 / 23.739 |
| Lỗi token / tổng token GT | 11.231 / 19.976 | 2.705 / 4.815 |
| Crop khớp hoàn toàn / crop đánh giá | 1.199 / 5.285 | 308 / 1.300 |
| Latency trung bình mỗi crop | 0,10024 giây | 0,09930 giây |
| Thời gian vòng inference của split | 530,07 giây | 129,16 giây |

Tổng thời gian hai vòng inference khoảng **659,23 giây**. Latency bao gồm khởi
động tiến trình Tesseract, kiểm tra ảnh và đọc TSV; không phải thời gian riêng
của mạng recognition. Máy có thể chạy tác vụ khác trong lúc benchmark, nên đây
là số liệu tham khảo cho môi trường đã ghi nhận, không phải phép đo hiệu năng cô lập.

## 2. Audit và protocol

- Đã giải mã, kiểm SHA-256 và kích thước **6.585/6.585 ảnh**; không ảnh hỏng,
  sai checksum/kích thước hay transcript rỗng/không hợp lệ.
- Đủ **5.285 train + 1.300 validation**, 6.585 ID duy nhất; không có nhóm trùng
  ảnh chính xác theo SHA-256 trong tập hoặc qua hai split.
- Đối chiếu toàn bộ manifest với hai file transcript nguồn: text, đường dẫn,
  dòng nguồn và split đều khớp; **0 sai khác**. Điều này xác nhận quá trình
  chuẩn bị giữ đúng nguồn, không chứng nhận nhãn nguồn đúng nội dung ảnh.
- Giữ nguyên hai split chính thức. Train là diagnostic; không tìm kiếm tham số
  hoặc fine-tune. Khóa PSM 7, model, protocol và checksum code trước inference.
- Xem trước 24 crop train theo seed 42 và nhóm kích thước đặc biệt. Phần lớn là
  một dòng/từ/số; có crop nhỏ, mờ và xoay. Review lỗi sau inference phát hiện cả
  crop nhiều dòng, cho thấy mẫu khảo sát ban đầu không đại diện mọi layout.
- Có **972 crop train và 245 crop validation cao tối đa 20 pixel**. Không có
  newline trong transcript không có nghĩa ảnh chỉ chứa một dòng chữ.

Normalization: Unicode NFKC, casefold, gộp khoảng trắng; giữ dấu tiếng Việt và
dấu câu. CER/WER dùng tổng edit distance chia tổng độ dài GT, không lấy trung
bình điểm từng crop. WER tách bằng khoảng trắng, thường tương ứng âm tiết tiếng
Việt. Exact-match so hai chuỗi sau normalization. Quy tắc GT rỗng, ảnh lỗi,
prediction thất bại và ID trùng nằm trong
[protocol đã khóa](WEEK2_RECOGNITION_PROTOCOL.md).

Repo đã có số liệu validation của một lượt PSM 6/7 trước đó. Lần này tái lập
baseline cố định và không chọn lại tham số từ kết quả validation; không tuyên bố
validation là tập chưa từng được xem. Chưa xác minh parent receipt/KIE của crop,
nên không suy rằng kiểm tra trùng byte đã loại mọi leakage ở cấp hóa đơn.

## 3. Phân tích trực quan 24 mẫu lỗi

Đã xem cả sáu contact sheet (24 crop train) và phóng lớn lại chín trường hợp
cần đọc kỹ. Tất cả mẫu có ảnh gốc, GT, prediction, CER/WER, nhóm chọn mẫu,
nhận xét riêng, trạng thái xác nhận và mức tin cậy trong artifact local.
GT gốc được giữ nguyên; không sửa điểm benchmark sau review.

| Nhận định chính trong bản phân tích | Số mẫu |
|---|---:|
| Lỗi nhận dạng, thường kèm chữ nhỏ/mờ/font khó | 10 |
| Có cả vấn đề nguồn/layout và lỗi OCR | 7 |
| Nghi transcript nguồn sai dấu, cần phân xử | 1 |
| Khác quy ước khoảng trắng/token hóa | 3 |
| Lỗi OCR kèm khác quy ước định dạng | 3 |
| **Tổng** | **24** |

Các nhóm được chọn có chủ đích, bốn mẫu mỗi nhóm: prediction rỗng, nghi lỗi dấu,
nghi spacing, nội dung số, chữ nhỏ và lỗi hỗn hợp lớn. Đây là nghiên cứu tình
huống, **không dùng các số đếm trên để ước lượng tỷ lệ lỗi toàn dataset**.

Những quan sát có tác động đến diễn giải kết quả:

1. **Hai crop nhiều dòng trả prediction rỗng.** PSM 7 giả định một dòng nên
   layout là một nguyên nhân khả dĩ. Cần khảo sát layout trên train ở thí nghiệm
   sau; không tự chuyển PSM trong benchmark đang chạy.
2. **Khoảng trắng làm WER tăng mạnh dù chữ số đúng.** Dấu cách quanh gạch nối
   hoặc dấu hai chấm có thể khác giữa nguồn và output. Một số ca còn bị OCR
   chèn khoảng trắng sát dấu phân cách giờ. Không diễn giải WER như tỷ lệ trường sai.
3. **Có sai khác transcript nguồn so với pixel.** Ví dụ GT thiếu từ hoặc thiếu
   dấu phân cách nhìn thấy trong ảnh; một số dấu/tháng còn mờ và chưa chắc chắn.
   Vì thế clean CER loại ảnh hưởng ghép vùng nhưng vẫn chịu chất lượng nhãn.
4. **Chữ nhỏ, nhòe, in chấm và logo nghiêng/cách điệu gây lỗi rõ rệt.** Review
   có trường hợp mất phần lớn ký tự, nhầm V/U, nhầm chữ số và nhầm dấu tiếng Việt.
   Các yếu tố cùng xuất hiện nên chưa xác định được đóng góp nhân quả riêng.
5. **Ca tiền tệ được xem có chữ số tiền đúng nhưng tiền tố tiền tệ sai.** Không
   dùng một lỗi tiền tố để kết luận giá trị tiền bị đọc sai. Các giá trị KIE
   chưa được đánh giá bằng benchmark recognition này.

Danh tính người xác nhận chưa được ghi nhận. Những case có
`label_uncertainty` hoặc mức tin cậy trung bình cần người kiểm tra trước khi
sửa nhãn. Mẫu review chỉ nằm trên train và không được dùng để thay cấu hình
validation trong lần chạy này.

## 4. Kiểm thử và kiểm chứng

**134 tests pass** trong toàn bộ suite, gồm các regression cho Unicode tổ hợp,
chèn/xóa/thay thế, chuỗi rỗng, CER lớn hơn 1, micro-averaging, exact-match,
exclusions, inference thiếu/thất bại, ID trùng/không tồn tại, ảnh hỏng, manifest
sai checksum/kích thước và trùng ảnh qua split.

`verify_recognition_benchmark.py` đã **pass 80 kiểm tra**: checksum đầu vào và
mã nguồn đúng bản khóa; số prediction/runtime/manifest khớp; không failure;
engine/model/PSM/OEM khớp; tính lại toàn bộ aggregate và per-crop metrics từ
predictions + manifest cho kết quả giống hệt. Đây là tái tính evaluator,
không phải chạy OCR lần hai và không phải đánh giá bằng thư viện metrics độc lập.

## 5. Môi trường và minh chứng

- Tesseract **v5.5.3.20260724**, `vie.traineddata` từ
  `tesseract-ocr/tessdata_fast@87416418657359cb625c412a48b6e1d6d41c29bd`.
- Model SHA-256:
  `79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1`.
- Manifest SHA-256:
  `159f17911783b6465f9b5ffd37de97d4a086722446aac05baf38e3997f8abf87`.
- Python **3.12.16**, Windows 11, **16 logical CPU**, Pillow 13.0.0,
  NumPy 2.3.5, OpenCV headless 4.14.0.94. `OMP_THREAD_LIMIT` không đặt.
- Git HEAD nền: `f88a4bfcefe87573f06c588bca3f7cbc4108c0da`; code Goal 1 là
  thay đổi local. `locked_config.json` lưu checksum từng file, kèm bản sao
  `source_snapshot/`; không coi HEAD nền là toàn bộ code đã chạy.
- Câu chữ về review được biên tập sau inference; `documentation_revisions.json`
  lưu checksum trước/sau của protocol. Checksum bản chạy trong `locked_config.json`
  vẫn giữ nguyên; bản sao protocol hiện tại là bản đã biên tập.

Bundle local: `outputs/ocr/week2/goal1_20261105/`.

| Artifact | Vai trò |
|---|---|
| `audit.json`, `audited_images.jsonl` | Kiểm tra ảnh, hash, kích thước, split, ID |
| `source_transcript_verification.json` | Đối chiếu 6.585 cặp với file nguồn |
| `train_layout_audit.png`, `train_layout_review.md` | Khảo sát dạng crop trước inference |
| `locked_config.json`, `source_snapshot/` | Cấu hình/model/code đã khóa |
| `documentation_revisions.json` | Lịch sử biên tập protocol sau inference |
| `official_train/`, `official_val/` | Predictions, failures, runtime, metrics, per-crop metrics |
| `error_review/index.html` | 24 ảnh và nhận xét trực quan có thể đọc local |
| `error_review/review_cases.json`, `.csv`, `review_summary.json` | Nhận định và mức tin cậy từng case |
| `verification.json`, `pytest.txt`, `tesseract_version.txt` | Kiểm chứng và môi trường |
| `artifact_manifest.json` | Checksum các file trong bundle, không tự bao gồm chính nó |

Ảnh, transcript, predictions và review chi tiết nằm trong `outputs/` bị Git
ignore. Báo cáo này chỉ chứa số liệu tổng hợp và phân tích giới hạn.

## 6. Chạy lại và phạm vi kết luận

Từ gốc repo, dùng một thư mục output mới:

```powershell
.\.venv\Scripts\python.exe scripts/run_recognition_benchmark.py --tesseract 'C:\Program Files\Tesseract-OCR\tesseract.exe' --output-dir outputs/ocr/week2/goal1_repeat
.\.venv\Scripts\python.exe scripts/verify_recognition_benchmark.py --run-dir outputs/ocr/week2/goal1_repeat
.\.venv\Scripts\python.exe scripts/review_recognition_errors.py --metrics outputs/ocr/week2/goal1_repeat/official_train/per_crop_metrics.jsonl --output-dir outputs/ocr/week2/goal1_repeat/error_review
```

Lệnh tạo review chỉ chọn mẫu và tạo ảnh; reviewer phải xem và ghi nhận xét mới
được tính là đã review. Hướng dẫn các bước riêng nằm trong [PIPELINE.md](PIPELINE.md).

Baseline trả lời được chất lượng nhận dạng crop theo protocol cố định. Không
so trực tiếp điểm này với CER toàn trang để suy mức cải thiện OCR, vì khác đơn
vị GT, tập ảnh và cách ghép. Các số crop trong tài liệu ngày 04/11 dùng Tesseract
5.3.4 là kết quả lịch sử ở môi trường khác; không trộn vào bundle hiện tại.
Không cần đạt ngưỡng CER cụ thể để hoàn thành Goal 1; mục tiêu là phép đo có
coverage rõ ràng, kiểm thử và minh chứng có thể kiểm tra lại.
