# OCR → Qwen local

## OCR sau pull ngày 15/11/2026

Entry Qwen hiện gọi PHOCR–VietOCR CUDA với `--scale-factor 2` (E1/Lanczos),
crop padding 10% có fallback 0% khi chạm vùng bên cạnh, theo commit `168c1a7`
và `baf232c`. `merged_predictions` là ghép text sau OCR, không đọc lại ảnh.
Cả baseline/refined nhận nhóm ghép như gợi ý tham chiếu về region gốc; không
nhét cả raw và merged thành hai bản bằng chứng lặp, không ép group thành tên.
Giữ polygon gốc vì union box của group không bảo toàn độ nghiêng từng dòng.

Xử lý ảnh bằng OCR hiện tại:

```powershell
.\.venv\Scripts\python.exe scripts/extract_receipt.py "data/mcocr/val_images/val_images/mcocr_val_145114ixmyt.jpg" --extraction-mode refined --output outputs/bill_refined.json
```

Baseline vẫn mặc định khi bỏ `--extraction-mode refined`; cả hai mode đều gọi
OCR E1 mới. Do thay OCR/payload, kết quả không còn là baseline OCR cũ cố định.
`--reuse-ocr` chỉ nhận runtime đúng profile E1/guarded-padding/merge hiện tại;
cache E0 cũ cần chạy OCR lại. Kiểm tra `ocr/runtime.json`, `ocr/predictions.jsonl`
(`merged_predictions`), và `inputs/<id>.json` (`ocr_merge_hints`, excluded merges).
Không có group ghép vẫn hợp lệ; không phải ảnh nào cũng cần merge.

Test adapter/profile: `tests/test_qwen_latest_ocr_contract.py`.
Một hạn chế OCR upstream: same-line merge dùng overlap y, có thể ghép nhầm các
dòng trên ảnh nghiêng; vì vậy Qwen chỉ dùng như gợi ý và giữ nguyên nguồn raw.

Xem [hướng dẫn refined](QWEN_GUARD_LAYOUT_REFINEMENT.md) để bật
`--extraction-mode refined`, dùng bbox/polygon và chọn source spans cho tên/địa chỉ.
CLI giữ baseline mặc định; web dùng refined. Các kết quả audit lịch sử bên
dưới thuộc phiên bản tương ứng của từng run.

Parser tiền hiện nhận phân nhóm bằng dấu cách thường/NBSP/narrow NBSP và đơn
vị gắn liền như `12.000đ`, `12.000d`, `12.000VND`. Ngày DMY dùng dấu chấm và
giờ dạng `08.29` được nhận khi đi cùng ngày; giá bán dạng `12.50` đứng riêng
không được coi là giờ. Dữ liệu thập phân không hỗ trợ vẫn cần rà soát.

Audit parser/guard mới:
`outputs/ocr_to_qwen/parser_guard_refactor/run_20261113/`.
`review.md` chấm tiền/ngày giờ bằng expected sidecar độc lập, `performance.json`
đo build/annotate, `new10/` giữ lượt mở rộng đầu và `final/` giữ lượt kiểm tra
lại sau sửa đơn vị tiền. Tập new10 đã dùng để sửa nên được xem là dev.

```powershell
.\.venv\Scripts\python.exe scripts/review_parser_run.py outputs/ocr_to_qwen/parser_guard_refactor/run_20261113
```

Lệnh trên chỉ chấm artifacts đã có, không chạy lại model. CLI một ảnh bên dưới
vẫn là lệnh sử dụng chính; JSON công khai không thêm metadata.

Nhãn tiền bị detector tách thành nhiều vùng (ví dụ `TỔNG` / `TIỀN` /
`PHẢI T.TOÁN`) được ghép theo hàng trước khi xác định vai trò. Các mảnh vẫn
giữ source ID và span trong `label_evidence`; cụm ghép nằm ở `label_phrase`
trong candidates. Chỉ ghép mảnh gần nhau và thẳng hàng với nhãn gốc để hạn chế
lan sang hàng giảm giá/khách trả. Audit ca validation `mcocr_val_145115vmgii.jpg`
và 15 ảnh hồi quy nằm ở `outputs/ocr_to_qwen/fragmented_label_fix/`.

## Một ảnh → JSON bốn field

Chạy trong repository root:

```powershell
.\.venv\Scripts\python.exe scripts/extract_receipt.py "C:\duong-dan\bien-lai.jpg" --output outputs/receipt.json
```

Lệnh tự tạo manifest cho ảnh, chạy OCR rồi Qwen CUDA tuần tự và in riêng JSON
bốn field ra stdout. `--output` lưu cùng JSON dưới UTF-8; bỏ tùy chọn này nếu
chỉ cần in. Log tiến trình được báo qua stderr, log chi tiết/artifacts ở
`outputs/ocr_to_qwen/single_receipt/`. Field chưa xác định giữ null.
Không chạy nhiều lệnh cùng lúc vì pipeline dùng chung cổng model local.
Lệnh dùng các môi trường/model đã cài; VietOCR có thể cần mạng để lấy config.

Kết quả gọn cho ứng dụng nằm ở `receipts/<image_id>.json`: chỉ có
`seller_name`, `seller_address`, `transaction_datetime`, `total_amount` với
giá trị đã chuẩn hóa. Giá trị chưa xác định giữ `null`. Demo có link **JSON 4 field**;
`extractions.jsonl` vẫn giữ thông tin audit để kiểm tra khi cần.

## Audit total_amount trên 15 ảnh

Lượt sửa mới nằm ở
`outputs/ocr_to_qwen/total_amount_audit_fix/run_20261113/release/index.html`.
Trang này liên kết sáu batch; mỗi batch có OCR JSON, request/response, raw selection,
final selection và quyết định guard. So sánh dùng lại OCR để đo riêng extraction.

Chạy lại vào thư mục mới, tuần tự trên CUDA:

```powershell
$auditRoot = "outputs/ocr_to_qwen/total_amount_audit_fix/my_$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -ItemType Directory -Path $auditRoot | Out-Null
Copy-Item -LiteralPath outputs/ocr_to_qwen/total_amount_audit_fix/run_20261113/release/sources.json -Destination "$auditRoot/sources.json"
.\.venv\Scripts\python.exe scripts/audit_total_amount.py $auditRoot --gpu
if ($LASTEXITCODE -ne 0) { throw "Audit failed; inspect batch logs" }
Start-Process (Join-Path $auditRoot "index.html")
```

Bỏ `--gpu` để chỉ replay lựa chọn đã lưu; đó không phải chạy model mới.
Expected tiền đọc độc lập từ annotation; các tranh chấp nhãn vẫn cần review ảnh.
Không chạy lại `--gpu` vào thư mục đã có kết quả. Đọc report về lỗi còn lại trước
khi suy rộng độ đúng từ bộ ảnh phát triển này.

## Tự test thêm 10 biên lai

Mở PowerShell trong repository root. Các lệnh sau chọn 10 ảnh internal_dev
khác 5 ảnh vừa test, không trùng checksum trong lượt mới, chia batch 3+3+3+1.
Seed cố định để tái hiện; không bảo đảm khác merchant/template. Chuẩn bị không
chạy GPU, không đổi model và không ghi đè output cũ.

```powershell
Set-Location C:\Python\AIO\DocuCheck-AI
$runRoot = "outputs/ocr_to_qwen/test_10_$(Get-Date -Format yyyyMMdd_HHmmss)"
.\.venv\Scripts\python.exe scripts/prepare_qwen_test_batch.py --count 10 --seed 42 --output-dir $runRoot
if ($LASTEXITCODE -ne 0) { throw "Khong tao duoc danh sach anh" }
```

Xem danh sách đã chọn trong `$runRoot/selection.json`. Sau đó chạy tuần tự:

```powershell
Get-ChildItem -LiteralPath $runRoot -Directory -Filter "batch_*" | Sort-Object Name | ForEach-Object {
    $batchPath = $_.FullName
    .\.venv\Scripts\python.exe scripts/demo_ocr_qwen.py --manifest "$batchPath/manifest.jsonl" --output-dir $batchPath
    if ($LASTEXITCODE -ne 0) { throw "Demo loi: $batchPath. Xem logs va extractions.jsonl" }
    .\.venv\Scripts\python.exe scripts/evaluate_qwen_demo.py $batchPath
    if ($LASTEXITCODE -ne 0) { throw "Danh gia loi: $batchPath" }
}
Start-Process (Join-Path $runRoot "index.html")
```

Pipeline chạy OCR GPU mới rồi giải phóng OCR trước khi nạp Qwen, mỗi batch
tối đa 3 ảnh. Không mở nhiều batch song song. Cần mạng khi VietOCR tải config.
Mỗi batch lưu demo.html, OCR JSON trong ocr/predictions.jsonl, kết quả trong
extractions.jsonl, phản hồi model ở responses/, quyết định sửa tiền ở decisions/,
đánh giá ở evaluation.json/report.md và logs/. Trang index nối bốn trang demo.

Để chọn 10 ảnh khác nữa, dùng output mới và seed khác, đồng thời thêm
`--exclude-manifest "$runRoot/manifest.jsonl"` vào lệnh chuẩn bị lượt tiếp theo.
Không chạy lại vào batch đã có extractions.jsonl vì CLI sẽ từ chối ghi đè.

Điểm evaluation là so nhãn dataset, chưa phải độ đúng thực tế. Đối chiếu ảnh
gốc khi lệch địa chỉ/chi nhánh/dấu; phân biệt lỗi OCR, lỗi Qwen và lỗi nhãn.
Không dùng audit_invoice_total_demo.py cho 10 ảnh này: script đó chỉ có expected
tham chiếu của 5 ảnh cũ. Nếu đang chỉnh prompt qua các ảnh mới, coi chúng là
dev, không báo là tập test độc lập.

## Tổng hóa đơn

`total_amount` là **Tổng hóa đơn**, sau giảm giá/thuế/phí ghi trên chứng từ và
trước khấu trừ đã trả/đặt cọc. Tiền đã thanh toán/còn lại/tiền thừa chỉ là ngữ
cảnh. Candidate giữ vai trò, số parse được và nguồn; kết quả lưu cả raw model
selection, final selection và `total_amount_decision`. Resolver chỉ sửa khi có
tổng in sẵn duy nhất rõ; mơ hồ thì cần review. Confidence vẫn là điểm OCR nguồn.

Demo mới: `outputs/ocr_to_qwen/invoice_total_fix/run_20261113/index.html`.
Lượt cuối: old_v2 (2 ảnh), new_v2 (3 ảnh); dùng lại OCR để so sánh extraction.

```powershell
.\.venv\Scripts\python.exe scripts/demo_ocr_qwen.py --manifest outputs/ocr_to_qwen/invoice_total_fix/run_20261113/old_v2/manifest.jsonl --output-dir outputs/ocr_to_qwen/invoice_total_my_run
```

Lệnh trên chạy OCR mới rồi model. Để tái dùng OCR, copy `ocr/` từ batch nguồn
vào thư mục output mới trước khi chạy, rồi thêm `--reuse-ocr`.
Server và client hiện cùng đọc context 8192 từ configs/qwen3_4b_q4_k_m.json.
Audit năm ảnh có thể chạy lại sau khi có old_v2/new_v2 tương ứng:

```powershell
.\.venv\Scripts\python.exe scripts/audit_invoice_total_demo.py outputs/ocr_to_qwen/invoice_total_fix/run_20261113
```

## Field selection v2

Schema 2.0: tên/tiền/ngày giờ chọn scalar candidate ID hoặc null; địa chỉ chọn
nhiều region ID. `value_raw` chỉ chứa các value spans; `evidence` giữ toàn vùng
OCR gốc. HTML hiển thị `display_value`. Context hiện tại 8192 do payload ứng
viên đầy đủ vượt 4096; Qwen vẫn offload 37/37 layers CUDA. Confidence substring
kế thừa điểm OCR vùng, không phải confidence riêng cho ký tự.

### Thứ tự các mảnh địa chỉ

Sau khi Qwen chọn các vùng `seller_address`, resolver dùng polygon gốc để
ước lượng độ nghiêng, gom các mảnh cùng dòng và sắp trái → phải trong dòng,
trên → dưới giữa các dòng. `value_raw`/`display_value` nối bằng khoảng trắng
trong một dòng và xuống dòng giữa các dòng; JSON bốn field vẫn trả địa chỉ
trên một dòng. Bước này giữ nguyên toàn bộ text/span/ID đã chọn.

`raw_model_selection` và `final_selection` giữ danh sách ID mà model/guard
trả về. Thứ tự dùng để ghép kết quả nằm ở
`fields.seller_address.reading_order.ordered_region_ids`; `line_region_ids`
ghi các nhóm dòng, `selected_region_ids` giữ thứ tự đầu vào. Vì vậy có thể
đối chiếu thay đổi thứ tự mà không nhầm thành model chọn vùng khác.
Các vùng chồng lấn nhiều hoặc có nhiều cách ghép dòng được gắn
`ambiguous_address_reading_order` để review; không xóa vùng để che lỗi.

Đây là bộ sắp xếp một khối địa chỉ có chữ gần ngang. Nó không sửa chữ OCR,
không bổ sung vùng Qwen bỏ sót, không loại nhãn/chi nhánh chọn nhầm và chưa
được xác minh cho nhiều cột, chữ dọc, giấy cong hoặc các dòng nghiêng khác nhau.
Demo và audit: `outputs/ocr_to_qwen/address_reading_order_fix/run_20261113/`.

Demo đã chạy:
`outputs/ocr_to_qwen/field_selection_fix/run_20261113/index.html`.
Chạy lại hai ảnh với OCR lưu sẵn bằng cách copy thư mục `ocr` vào output mới
rồi dùng `--reuse-ocr`; chạy OCR mới thì bỏ cờ này:

```powershell
.\.venv\Scripts\python.exe scripts/demo_ocr_qwen.py --manifest outputs/ocr_to_qwen/field_selection_fix/run_20261113/new/manifest.jsonl --output-dir outputs/ocr_to_qwen/my_new_fix_run
.\.venv\Scripts\python.exe scripts/evaluate_qwen_demo.py outputs/ocr_to_qwen/my_new_fix_run
```

Giới hạn còn lại: nhóm tên là lựa chọn hình học đơn giản; chưa có resolver tên
substring trong dòng chứa lẫn tên/địa chỉ. Ngày chỉ có giờ chưa tạo ứng viên;
ghép ngày/giờ khác vùng còn dùng quan hệ gần và cần audit nhiều mẫu. Không coi
bộ candidate này là đã bao phủ mọi trường hợp trong prompt. Xem audit.md.

Chạy từ repository root bằng PowerShell. Model và runtime chỉ nằm trong outputs.

```powershell
.\.venv\Scripts\python.exe scripts/download_qwen_model.py
.\.venv\Scripts\python.exe scripts/demo_ocr_qwen.py --manifest outputs/ocr_to_qwen/demo_20261113/manifest.jsonl --output-dir outputs/ocr_to_qwen/my_new_run
.\.venv\Scripts\python.exe scripts/evaluate_qwen_demo.py outputs/ocr_to_qwen/my_new_run
```

Manifest demo có hai receipt đã chọn trước inference. Dùng output directory mới
mỗi lần. Môi trường `.venv-phocr-gpu` cần torch CUDA, ONNX Runtime CUDA, PHOCR
và VietOCR tương thích. Wrapper run_ocr_cuda nạp torch trước ONNX, kiểm tra
providers trên session thực; giữ nguyên detector và recognizer đang có.
VietOCR tải config từ vocr.vn khi khởi tạo nên có thể cần mạng.

Nếu đã chạy server local, trích xuất JSON OCR có sẵn:

```powershell
.\outputs\runtime\llama-b12345\llama-server.exe -m outputs/models/qwen3_4b_instruct_2507/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf -ngl 99 -c 8192 -np 1 -b 256 -ub 128 --host 127.0.0.1 --port 8097 --jinja -lv 4
.\.venv\Scripts\python.exe scripts/extract_receipt_fields.py --ocr outputs/ocr_to_qwen/demo_20261113/ocr/predictions.jsonl --manifest outputs/ocr_to_qwen/demo_20261113/manifest.jsonl --output-dir outputs/ocr_to_qwen/manual_new_run --image-id 06f4a47f229eed1d676fab46
```

Lệnh server cần terminal riêng; dừng Ctrl+C sau khi chạy xong. Lệnh demo tự quản
lý và dừng server của nó. File GGUF đúng SHA được ghi trong config/download.json.
Toàn bộ chat template thực tế nằm trong server_props.json; request lưu prompt,
schema và tham số. Bộ nhớ runtime lấy mẫu mỗi giây, không phải peak tuyệt đối.

Demo đầu lưu ở demo_20261113; lần sửa prompt và chuẩn hóa tiền nhiều vùng lưu
ở demo_20261113_v2, sử dụng lại đúng OCR GPU mới của lượt đầu. Kết quả v2 vẫn
có lỗi chọn tên và tiền; xem report.md/evaluation.json. Test kỹ thuật không
chứng minh độ chính xác. Confidence trên HTML là min điểm OCR bằng chứng,
không phải xác suất Qwen đúng. Nếu thiếu một confidence thành phần thì null.

Đối chiếu GT chạy riêng sau prediction. Quy tắc đánh giá nằm trong evaluation.json.
Không dùng ảnh đã chỉnh prompt làm tập kiểm thử cuối cho benchmark tương lai.
