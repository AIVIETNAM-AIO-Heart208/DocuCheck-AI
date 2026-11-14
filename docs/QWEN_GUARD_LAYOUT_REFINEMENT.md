# OCR → Qwen: Guard và layout refined

## Trạng thái bàn giao

Đã viết code và test; **chưa chạy test, replay, OCR, model hoặc benchmark**.
Mặc định là `baseline`. Chưa đạt điều kiện đổi mặc định hay kết luận tăng độ đúng.
Baseline lúc bắt đầu: commit `22643782c2725c5b546a6951da5572140f1e3e79`;
working tree chỉ có prompt refinement chưa track. Không dùng kết quả GPU/test
của các thí nghiệm cũ để xác nhận code mới.

## Những thay đổi đã triển khai

- `QwenClient(extraction_mode="baseline" | "refined")`, truyền xuyên cả ba CLI.
  Nhánh baseline tiếp tục dùng candidates/prompt/schema/semantic guard cũ.
- Refined dùng polygon pixel và bộ deskew hiện có; nếu thiếu polygon thì dùng
  bbox cho toàn tập. Chia dòng ở khoảng trống lớn, nối các dòng gần/căn lề thành
  giả thuyết khối. Lưu tọa độ sau chiếu và đơn vị, không ghi đè OCR.
- Tạo phương án dòng và cửa sổ 2–3 dòng, tối đa 256 phương án. Không sinh powerset.
  Mọi region gốc vẫn vào request; tên/địa chỉ được chọn trực tiếp bằng span nên
  không bị giới hạn bởi các ứng viên N singleton/cặp dọc. Registry N cũ được lưu
  để truy nguyên, nhưng không đưa các N ID đó vào schema refined.
- Schema 3.1: Qwen chọn tên/địa chỉ bằng mảng ID văn bản (`["R003"]`, hoặc
  ID phần chữ `R003:P1` được code cung cấp), không sinh offsets. Code ánh xạ ID
  về spans có offsets tính theo Unicode code point của text gốc. Validator kiểm
  tra nguồn, biên, span trùng/chồng. Hai field có thể dùng hai đoạn khác nhau
  trong một box. Code sắp lại vùng bằng polygon; không sửa chữ/số nhà.
- Ghép các text ID bằng khoảng trắng. Chưa tự sửa từ bị cắt giữa từ; helper nội
  bộ vẫn hỗ trợ join rỗng có review, nhưng không cho model tự sinh joiner/offset.
  Nhiều block, hình học mơ hồ hoặc tên/địa chỉ chồng span tạo needs_review.
- Guard refined dùng nhiều giả thuyết nhãn Việt/Anh, giữ nguyên lựa chọn Qwen,
  không tự điền model null, không phủ quyết chỉ vì unknown/cột phải/tổng khác.
  Không bật veto số học vì chưa xác minh được điều kiện chỉ thanh toán tiền mặt.
  Bản đầu chỉ cảnh báo ngữ nghĩa; vì vậy số OCR sai vẫn có thể được giữ lại.
- Lỗi bằng chứng được cô lập theo field; các field khác vẫn có thể xuất được.
  Schema toàn response sai hoặc response bị cắt vẫn là lỗi cả lượt.
- Giữ context 8192, reserve output 512, một completion/lượt; vượt budget báo lỗi,
  không cắt hoặc tự fallback. Thêm dữ liệu layout có thể tăng token; chưa đo mức tăng.
- Payload compact v2 lưu text/bbox một lần, nhãn tham chiếu `[region_id,start,end]`,
  dòng/khối tham chiếu ID. Phương án ghép dòng suy ra được từ cấu trúc chỉ giữ
  trong layout ledger; mọi vùng vẫn chọn trực tiếp được. Run đầu người dùng chạy
  có 8734 prompt token + 512 output, vượt 8192. Đã sửa serialization; chưa chạy
  lại tokenizer/model để xác nhận token mới hoặc kết quả inference.
- Run tiếp theo của người dùng đã vào được model với 4228 prompt token, nhưng
  model dùng bbox `198..352` làm offsets của `Vincommerce` dài 11 ký tự, khiến
  hai field tên/địa chỉ bị validator loại; tiền/ngày do model tự chọn null.
  Đã thay schema bằng enum text ID và thêm text trực tiếp cho ứng viên tiền/ngày.
  Chưa chạy lại model/test để xác nhận schema 3.1 cải thiện lựa chọn thực tế.
- Payload hiện tại `readable_text_ids_v3` bỏ offsets khỏi prompt, hiển thị trực
  tiếp giá trị ứng viên scalar và text nhãn đã liên kết. Offsets đầy đủ vẫn nằm
  trong registry/diagnostics. Những mô tả v2 phía trên chỉ ghi lịch sử sự cố.
  Mọi field model chọn rỗng/null có issue `model_abstained`; receipt-level `ok`
  không đồng nghĩa các field đã được tìm thấy hoặc đúng. `field_validation_failed`
  cho biết có field bị loại do bằng chứng không hợp lệ.
- Retry OCR/model tự động chưa triển khai. Diagnostics cho biết retry không chạy.
  Giữ đường PHOCR–VietOCR hiện tại, padding/scale và cách chạy GPU tuần tự.

`status: ok` ở cấp receipt biểu thị response được xử lý, không phải xác nhận bốn
field đúng. `needs_review` có thể vẫn giữ giá trị. JSON công khai chỉ bốn field;
hãy đọc `extractions.jsonl`/demo và cảnh báo stderr để thấy trạng thái.

## Demo một ảnh — người dùng tự chạy

Các lệnh dưới **chưa được thực thi**. Dùng terminal PowerShell tại repo; cần
weights Qwen, runtime CUDA và môi trường OCR hiện có. Không cần tải model mới.

```powershell
Set-Location C:\Python\AIO\DocuCheck-AI
.\.venv\Scripts\python.exe scripts/extract_receipt.py "data/mcocr/val_images/val_images/mcocr_val_145114qwedt.jpg" --extraction-mode refined --output outputs/bill_refined.json
```

CLI in đường dẫn thư mục run/log/diagnostics qua stderr, stdout chứa JSON bốn
field. Mở `demo.html` trong thư mục run được báo. Các file quan trọng:

| File | Nội dung |
|---|---|
| `ocr/predictions.jsonl`, `ocr/runtime.json` | OCR và preprocessing thực tế |
| `provenance.json` | Commit, hash source/config/OCR/manifest, metadata OCR; không xác nhận lại hash weights |
| `inputs/<id>.json` | Mapping OCR và kích thước ảnh |
| `layout/<id>.json` | Dòng, khối, phương án bị lược, ngưỡng và giới hạn |
| `candidates/<id>.json` | Registry ứng viên scalar gốc |
| `text_spans/<id>.json` | Ánh xạ text ID → region và span chính xác |
| `coverage/<id>.json` | ID thực sự vào request, token, budget; không phải điểm coverage theo nhãn |
| `requests/<id>.json`, `responses/<id>.json` | Request và response Qwen |
| `decisions/<id>.json`, `extractions.jsonl` | Raw/final, spans, Guard, issues, trạng thái |
| `receipts/<id>.json` | JSON công khai bốn field |

Trở lại baseline bằng `--extraction-mode baseline` hoặc bỏ tùy chọn mode.
Mỗi lần chạy một ảnh tạo thư mục mới. Các lần gọi CLI độc lập vẫn nạp model lại;
thay đổi này không triển khai persistent service.

## So sánh bằng cùng OCR, không chạy detector lần nữa

Dùng manifest 1–3 ảnh và một OCR run đã có. Thay các đường dẫn ví dụ bằng run
thực tế. Chọn hai thư mục output mới; chạy tuần tự để tránh tranh VRAM.

```powershell
$ocrRun = "outputs/ocr_to_qwen/single_receipt/THU_MUC_RUN_DA_CO"
$manifest = "$ocrRun/manifest.jsonl"
$before = "outputs/ocr_to_qwen/guard_layout_refinement/baseline_01"
$after = "outputs/ocr_to_qwen/guard_layout_refinement/refined_01"
New-Item -ItemType Directory -Path "$before/ocr", "$after/ocr"
Copy-Item -LiteralPath "$ocrRun/ocr/predictions.jsonl" -Destination "$before/ocr/predictions.jsonl"
Copy-Item -LiteralPath "$ocrRun/ocr/predictions.jsonl" -Destination "$after/ocr/predictions.jsonl"
Copy-Item -LiteralPath "$ocrRun/ocr/runtime.json" -Destination "$before/ocr/runtime.json"
Copy-Item -LiteralPath "$ocrRun/ocr/runtime.json" -Destination "$after/ocr/runtime.json"
.\.venv\Scripts\python.exe scripts/demo_ocr_qwen.py --manifest $manifest --output-dir $before --reuse-ocr --extraction-mode baseline
.\.venv\Scripts\python.exe scripts/demo_ocr_qwen.py --manifest $manifest --output-dir $after --reuse-ocr --extraction-mode refined
.\.venv\Scripts\python.exe scripts/review_guard_layout.py $before --after $after --output outputs/guard_layout_comparison_01.json
```

Cả hai lệnh demo đều gọi Qwen CUDA thật khi bạn thực thi. Script review chỉ đọc
file, yêu cầu hash OCR giống nhau; báo thay đổi và lỗi/mẫu thiếu. Chưa có reference
thì chưa chấm đúng/sai. Có thể thêm `--reference path/to/frozen_reference.json`:

```json
{"image_id_thuc_te": {"seller_name": "Tên đã review", "total_amount": 35000}}
```

Reference phải khóa độc lập trước khi xem output; field không có đáp án bỏ qua
chấm điểm, không coi là pass. Script so sánh giá trị exact và báo regression từng
field; việc review ảnh, sai chủ thể, thiếu/thừa thành phần và nhãn sai còn thủ công.
Lỗi cả receipt được liệt kê riêng, phải tính vào mẫu số audit cuối.

Replay riêng chính sách Guard, không đánh giá khả năng chọn layout mới:

```powershell
.\.venv\Scripts\python.exe scripts/review_guard_layout.py $before --replay-guard --output outputs/guard_layout_replay_01.json
```

Replay dùng raw IDs với registry của chính run đó, không remap vào registry mới
và không gọi network/model. Lệnh này cũng chưa được chạy.

Nếu bạn có server CUDA đang chạy và muốn dùng OCR cũ trực tiếp:

```powershell
.\.venv\Scripts\python.exe scripts/extract_receipt_fields.py --ocr "$ocrRun/ocr/predictions.jsonl" --manifest $manifest --output-dir outputs/ocr_to_qwen/guard_layout_refinement/existing_server_01 --extraction-mode refined --base-url http://127.0.0.1:8097
```

## Test đã viết và lệnh tự kiểm chứng

File mới `tests/test_guard_layout_refinement.py` có các ca tách ngang, nghiêng/
scale/permutation, tách cột, từ lặp, span tên/địa chỉ chung region, nối trong từ,
nhãn Anh/Việt, vai trò xung đột, giữ model null, default mode, cô lập lỗi field và
context preflight. Chưa chạy; không được xem danh sách này là kết quả pass.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_guard_layout_refinement.py tests/test_qwen_candidates.py tests/test_qwen_extraction.py tests/test_invoice_total.py tests/test_total_amount_relations.py tests/test_address_reading_order.py tests/test_ocr_hybrid.py
```

## Giới hạn và điều kiện trước khi đổi mặc định

- Geometry là giả thuyết từ một góc nghiêng chung và ngưỡng tương đối; chưa có
  hiệu chỉnh phối cảnh mạnh, giấy cong, chữ dọc/ảnh phản chiếu hoặc xoay 90/180°.
  Bbox ngang không chứa đủ thông tin để phục hồi mọi góc chữ. Không có cơ chế
  tự phát hiện đáng tin cậy tất cả các trường hợp ngoài phạm vi.
- Phân khối hình học chưa xác nhận thực thể. Footer và header đều có thể có địa
  chỉ hợp lệ; Qwen vẫn có thể chọn nhầm hoặc bỏ dòng. Flag nhiều khối không đủ
  phát hiện mọi sai chủ thể. Độ đầy đủ so với ảnh luôn ghi chưa xác minh.
- Baseline giữ quan hệ nhãn–giá trị gốc. Refined bổ sung các anchor giả thuyết
  cùng hàng và dòng trên từ layout; chúng vẫn có thể sai, không xác nhận vai trò.
- Không có veto ngữ nghĩa đã được chứng minh an toàn. Guard advisory có thể để
  lọt tiền OCR sai; nhận dạng chính xác và arithmetic safety chưa được xác nhận.
- Việc tự phục hồi ranh giới trong một từ chưa triển khai trong schema ID mới;
  không phục hồi chữ mà detector/recognizer đã làm mất.
- Schema text ID mới và grammar llama.cpp thực tế chưa kiểm chứng. Model không
  còn được phép tự sinh offsets; các phần chữ tùy chọn được code chia theo dấu
  phân cách/nhãn inline, chưa bao phủ mọi box trộn tên–địa chỉ không có ranh giới.
  Output 512 token có thể không đủ cho hóa đơn chia quá vụn;
  response bị cắt sẽ báo lỗi, không tự tăng budget hoặc suy diễn phần còn lại.
- Chưa có benchmark độc lập, coverage theo nhãn/ảnh, regression, latency hoặc
  VRAM mới. Bộ test chưa bao phủ toàn bộ ma trận trường hợp của prompt; cần bổ
  sung fixture thực tế khi người dùng xác nhận nhóm ảnh và đáp án.

Chỉ đề xuất đổi default sau test phù hợp pass, replay không hại đáp án đúng,
Qwen CUDA thật cải thiện selection tên/địa chỉ trên OCR cố định, không regression
bốn field/context/false non-null, và có đánh giá ảnh chưa dùng chỉnh rule. Hiện
mọi điều kiện thực nghiệm đó đều **chưa xác minh**; giữ baseline mặc định.
