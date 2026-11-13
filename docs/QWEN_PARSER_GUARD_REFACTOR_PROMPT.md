# Rà soát và sửa parser/guard OCR → Qwen theo ngữ cảnh, có kiểm chứng tổng quát

Bạn là kỹ sư Python phụ trách DocuCheck-AI. Hãy đọc code và artifacts thực tế,
triển khai sửa lỗi, chạy kiểm thử, replay và Qwen CUDA thật. Không dừng ở kế
hoạch hay sửa vài dòng prompt. Mục tiêu là tăng độ bao phủ của parser tiền,
ngày giờ và độ đúng của guard, có kiểm soát regression và chi phí chạy.

## 1. Phạm vi và nguyên tắc không hardcode theo mẫu

- Giữ API bốn field: `seller_name`, `seller_address`, `transaction_datetime`,
  `total_amount`. JSON cho người dùng chỉ chứa bốn field với giá trị chuẩn hóa;
  thông tin chẩn đoán ở artifacts riêng. Giữ CLI một ảnh → JSON đang có.
- `total_amount` là tổng cuối hóa đơn sau giảm giá/thuế/phí in trên chứng từ,
  trước khấu trừ đặt cọc/đã trả để tính dư nợ. Không đổi nghiệp vụ cho khớp nhãn.
- Không đặt điều kiện production theo image_id, filename, checksum, merchant,
  logo, candidate ID, số tiền, ngày giờ hoặc tọa độ cố định của một mẫu.
  Giá trị tham chiếu chỉ được nằm trong fixtures/evaluation, không vào inference.
- Ngữ pháp số/ngày, từ vựng nghiệp vụ và ngưỡng hình học tổng quát được phép dùng.
  Mỗi luật phải có ý nghĩa, phạm vi áp dụng, dấu hiệu phản đối và test dương/âm.
  Không biến dictionary từ khóa thành điều kiện bắt buộc duy nhất để chấp nhận
  lựa chọn model; không thêm synonym chỉ để vượt qua một bill rồi dừng.
- Không dùng GT, expected hoặc ảnh đã gán đáp án để sửa lựa chọn tại runtime.
  Không bịa tiền, sửa chữ số OCR, lấy số lớn nhất/cuối cùng hay tự cộng tiền
  thanh toán để tạo một tổng không xuất hiện trong OCR.
- Giữ Qwen3-4B-Instruct-2507 Q4_K_M và OCR hiện tại. Sửa parser/guard trước;
  không đổi model, fine-tune hoặc thêm framework nặng để né lỗi xử lý.
- Phạm vi chính là tiền và transaction_datetime cùng quan hệ nhãn cần thiết.
  Kiểm tra cả tên/địa chỉ vì thay đổi payload có thể làm model đổi các field đó.
  Không tự mở rộng sang viết lại OCR, seller extractor hoặc giao diện.

## 2. Đọc repository và cố định baseline

Đọc AGENTS.md nếu có, git status và các file sau trước khi sửa:

- `src/docucheck/extraction/money.py`, `candidates.py`, `relations.py`,
  `invoice_total.py`, `qwen.py`, `export.py`.
- `scripts/extract_receipt.py`, `extract_receipt_fields.py`, `demo_ocr_qwen.py`,
  `run_ocr_cuda.py`, `audit_total_amount.py`, `evaluate_qwen_demo.py`.
- Các tests parser/candidates/relations/guard/Qwen, config model và
  `docs/QWEN_DEMO.md`. Prompt trước là lịch sử, cần đối chiếu code hiện tại.

Giữ thay đổi chưa commit của người dùng, đặc biệt bản ghép nhãn phân mảnh vừa
sửa. Không reset/clean. Tạo run mới trong
`outputs/ocr_to_qwen/parser_guard_refactor/<run_id>/` và chụp snapshot code,
prompt, config, manifest, OCR hash trước chỉnh sửa. Không ghi đè artifacts cũ.

Baseline chính gồm **17 ảnh riêng biệt**:

1. 16 ảnh ở `outputs/ocr_to_qwen/fragmented_label_fix/batch_01/` đến `batch_07/`.
   Đây là kết quả sau sửa nhãn tách vùng, bao gồm bill_01 VinCommerce.
2. Bill_02 Coffee House: image_id `69df4b639fb0cee8dbe1898a`, artifacts đã biết:
   `outputs/ocr_to_qwen/single_receipt/69df4b639fb0cee8dbe1898a_zifu1wi3/`.
   Nếu đường dẫn khác, tìm manifest theo image_id/ảnh; không chọn nhầm run.

Xác nhận 17 image_id và checksum ảnh không trùng. Artifacts lịch sử ở
`total_amount_audit_fix/run_20261113/release/` dùng để truy nguyên, không dùng
thay cho baseline gần nhất để báo lại cải thiện đã có từ lượt trước.
Lưu provenance nào xác minh được; không mặc nhiên gán code hiện tại cho run cũ.

## 3. Tái hiện các lỗi đã biết trước khi sửa

### Bill_02: chữ OCR đã có nhưng parser/guard làm mất dữ liệu

Trong lượt đã đọc, OCR chứa:

```text
R005: Thời gian:30.09.2020 08.29 Số HĐ: 19809053062020
R019: Thành tiền:
R020: 35000
R021: Thanh Toán:
R022: 35 000
R023: Tiền khách đưa:
R024: 100000
R025: Tiền thừa:
R026: 65.000
R027: % Tiền mặt VND
R028: 35 000
```

- Model chọn M011 → R020 `35000`, nhãn `Thành tiền:`: chọn đúng nguồn tổng.
  Guard gán role unknown, rồi trả null với `invoice_total_not_unambiguous`.
- `35 000` bị tạo thành ứng viên `35` và `000`; đây là lỗi tokenization.
- Nhóm datetime rỗng vì chưa nhận `30.09.2020 08.29`.
- Expected review từ ảnh: total_amount **35000**, datetime
  **2020-09-30T08:29**. Những giá trị này chỉ dùng chấm sau inference.

### Bill_01 và các hồi quy quan trọng

- `0a54b1dd696fac0a2465195a`: nhãn `TỔNG` / `TIẾN` / `PHẢI T. TOÁN`
  tách nhiều region; bản gần nhất đã giữ đúng **6000**. Bảo toàn cách ghép
  có source spans, không ép detector phải luôn xuất nguyên một dòng.
- Runa: tổng 1.300.000, đặt cọc/đã trả/còn lại có các dòng 650.000.
  Không chọn 650.000 chỉ vì nằm gần cuối hoặc chứa “thanh toán”.
- Các ca 190.000, 40.000, 49.500, 151.825, 184.500 từng bị nhãn tổng lan sang
  số lượng hoặc giảm giá. Không tái tạo xung đột giả khi mở rộng parser.
- `3bfe5923d44b0bde3892ebfc`: “Cộng tiền hàng” 22.300 là tổng cuối của hóa đơn
  đơn giản; annotation lặp số. Không mặc định subtotal luôn sai hoặc luôn đúng.
- `1b4f9e96ca489a058e41d461`: OCR ảnh xoay thiếu 42.600; giữ khả năng abstain.
- `da51b171c389944c0a4e98ee`: OCR đọc 132.000 thành 9.132.000; không tự cắt
  số 9. Số tiền khách đưa/tiền thừa chỉ hỗ trợ phát hiện mâu thuẫn có căn cứ.
- Tiền mặt, tiền thừa từng bị OCR sai làm luật số học chặn tổng đúng.
  Không khôi phục kiểm tra bằng phép bằng tuyệt đối vô điều kiện.

Các ID/giá trị trên là mốc audit, tuyệt đối không là điều kiện chọn production.
Viết test tái hiện ít nhất ba lỗi bill_02 và chứng minh đỏ trên snapshot trước
sửa. Bản sửa phải giữ các test bảo vệ bill_01 và các regression tiền đã có.

## 4. Thiết kế parser có contract chung

Tách rõ: nhận dạng token/spans → diễn giải giá trị/độ mơ hồ → đánh giá vai trò
và quan hệ → model chọn → kiểm tra cuối → export. Dùng cùng nguồn parser cho
builder và resolver để tránh builder nhận một format nhưng normalize từ chối.
Evaluator phải độc lập với nguồn parser đó.

Kết quả parse cần biểu diễn được raw text, exact source spans, normalized value,
loại token, format/precision, trạng thái valid/ambiguous/invalid và lý do.
Dùng cấu trúc nhỏ có type hints; không thay toàn bộ kiến trúc nếu không cần.
Chỉ thêm schema nội bộ khi có ích, giữ public JSON tương thích.

### 4.1. Tiền: phân biệt phân nhóm nghìn với nhiều giá trị

- Hỗ trợ số nguyên có/không phân nhóm, dấu `.`/`,`, dấu cách thường và khoảng
  trắng Unicode phù hợp như NBSP U+00A0, narrow NBSP U+202F. Trong ngữ cảnh tiền
  rõ, `35 000`, `35.000`, `35,000`, `35000` phải cùng giá trị 35000.
- Không xóa toàn bộ khoảng trắng rồi nối mọi số: phân biệt `2 35 000` có thể
  là quantity + price; `650000 650000` là hai số; nhiều cột/dòng không là một số.
  Không nối qua newline, nhãn, dấu phân cột hoặc khoảng cách hình học không hợp lệ.
- Quét token đầy đủ trước khi chuẩn hóa. Không nhận một phần `1111,990`, số GD,
  barcode, số điện thoại, ngày/giờ hay số nhà thành một tổng hợp lệ khác.
  Nếu token phân mảnh qua nhiều region, chỉ ghép khi có bằng chứng một giá trị;
  lưu từng span và ngăn ghép nhầm số lượng/đơn giá/thành tiền.
- Nhận đơn vị tiền gắn liền/tách khỏi số như `đ`, `₫`, `VND` khi có căn cứ;
  giữ đơn vị, format trong audit. Dấu trừ/zero không bị mất vì truthiness.
- Phần thập phân rõ `.00`/`,00` có thể chuẩn hóa integer tương thích. Với
  phần lẻ khác 0 hoặc tiền tệ ngoài phạm vi VND integer, báo không hỗ trợ/mơ hồ,
  giữ raw và candidate audit; không làm tròn, nhân 100 hay đổi currency ngầm.
  Dùng Decimal nếu cần phân tích phần lẻ, không dùng binary float cho tiền.
- Format hỗn hợp `1.300,000` đã có test tương thích; xác định rõ chính sách
  format theo contract hiện có, không thêm ngoại lệ theo merchant/số cụ thể.
  Tách format đã hỗ trợ khỏi format chưa đủ căn cứ; không tuyên bố hỗ trợ mọi locale.
- Không để một span đồng thời thành giờ và tiền được xác nhận chỉ vì regex
  đều match. Có cơ chế xét vai trò/ưu tiên theo ngữ cảnh; ghi ambiguity nếu thiếu.

### 4.2. Ngày giờ: format rộng hơn nhưng không nhận nhầm số tiền hoặc mã

- Hỗ trợ DMY với `/`, `-`, `.` và năm bốn chữ số; ISO YMD rõ ràng nếu gặp.
  Hỗ trợ giờ `HH:mm`, `HH:mm:ss`, `HH.mm` trong ngữ cảnh thời gian rõ; các
  biến thể `HHhmm` hoặc dấu cách quanh delimiter cần chính sách có test.
- `08.29` được hiểu là giờ khi nằm trong cụm thời gian hợp lệ như cạnh ngày
  và nhãn giao dịch; không tự coi mọi `12.50` hoặc mã hàng có dấu chấm là giờ.
  Date/time patterns phải chống match substring trong chuỗi dài và lẫn với nhau.
- Kiểm tra ngày tồn tại, năm nhuận và giờ/phút/giây. Không sửa ngày 31/02,
  giờ 25:70, tự gán thế kỷ cho năm hai chữ số hoặc đảo ngày/tháng thiếu policy.
- Chọn ngày giờ giao dịch theo nhãn và vị trí tương đối; phân biệt HSD/NSX,
  ngày in lại, ngày giao hàng, số hóa đơn/GD trên cùng dòng.
- Ghép ngày và giờ khác region bằng quan hệ có bằng chứng, không lấy giờ
  đầu tiên trong thứ tự dict. Nếu có nhiều cặp hợp lý, giữ phương án rõ để
  model chọn hoặc needs_review; không âm thầm lấy phần tử đầu tiên.
- Giá trị chỉ chứa date/time spans, không chứa “Số HĐ” hoặc mã giao dịch.
  Giữ precision date/minute/second từ kết quả parse thay vì đoán bằng dấu `:`.
  Ví dụ `08.29` phải xuất `T08:29` với precision minute, không bị gắn precision date.
- Không bịa thời gian thiếu. Date-only giữ chính sách hiện hành với issue
  thiếu giờ; time-only phải có trạng thái rõ, không ghép ngày hôm nay hay ngày
  ở vùng không liên quan. Không tự gắn timezone nếu nguồn không cung cấp.
- NFKC/chuẩn hóa Unicode không được làm lệch index source spans. Mapping từ
  chuỗi chuẩn hóa về chuỗi OCR gốc phải được kiểm chứng khi độ dài thay đổi.

## 5. Quan hệ, vai trò và guard theo bằng chứng

### 5.1. Dùng nhãn và bố cục cùng nhau

- Bảo toàn nhãn nguyên dòng lẫn nhãn bị tách nhiều mảnh; có một biểu diễn cụm
  nhãn nhất quán cho model, role inference và guard, cùng nguồn từng mảnh.
  Guard kiểm tra lại từng fragment riêng sẽ tái tạo lỗi vừa sửa.
- Phân biệt “Thành tiền” trong từng dòng hàng/cột bảng với “Thành tiền” tổng
  kết hóa đơn. “Thanh toán” có thể là tổng phải trả, đã trả hoặc phương thức;
  phải xét quan hệ với hàng hàng hóa, subtotal/discount/tax và khu thanh toán.
- Từ khóa là bằng chứng hỗ trợ/đối lập, không là chân lý duy nhất. Nhãn chưa
  biết không đồng nghĩa giá trị sai; nhãn chứa “tổng” không tự xác nhận giá trị.
  Nếu có nhiều ngữ nghĩa thật sự mâu thuẫn, lưu các giả thuyết và lý do.
- Phân biệt `cash_tendered` (khách đưa), số đã thanh toán và khoản áp dụng bằng
  tiền mặt/thẻ. Ở bill_02, khách đưa 100.000, tiền thừa 65.000, tiền mặt 35.000
  không phải ba giá trị tiền đưa. Không gộp “tiền mặt/tiền thẻ” luôn vào tendered.
- Số lượng và tiền không thể phân biệt chỉ nhờ có dấu chấm/phẩy. Thay heuristic
  “ứng viên có delimiter duy nhất là tiền” bằng bằng chứng cột/nhãn/đơn vị/ngữ cảnh;
  kiểm tra số tổng viết liền `35000` và giá trị 0, âm, nhỏ vẫn có thể hợp lệ.
- Không group nhãn chỉ bằng region đầu tiên nếu nhãn có nhiều fragment.
  Ghi quan hệ yếu, mâu thuẫn và phương án bị bỏ; confidence OCR không phải
  confidence lựa chọn, score heuristic cũng không phải xác suất đã hiệu chuẩn.

### 5.2. Decision policy cụ thể, không guard bằng keyword whitelist

Viết decision table ngắn và tests trước khi triển khai. Tối thiểu:

| Bằng chứng | Hành động |
|---|---|
| ID/span/schema không hợp lệ, parse không xác định được giá trị | Reject/needs_review với reason; không xuất success giả. |
| Model chọn giá trị hợp lệ và ngữ cảnh hỗ trợ, dictionary chưa có nhãn | Không null chỉ vì role unknown; quyết định theo bằng chứng đã định nghĩa. |
| Tổng có bằng chứng tốt, đối thủ chỉ là quan hệ yếu/sai hàng/số lượng | Không cho đối thủ yếu phủ quyết đáp án đúng. |
| Model chọn paid/deposit/change, có tổng cuối rõ và không mâu thuẫn mạnh | Có thể override; lưu raw selection, source, reason và phản chứng. |
| Hai tổng khác nhau đều có bằng chứng mạnh | Phân biệt subtotal/final bằng ngữ cảnh; không được thì abstain. |
| Nhiều nguồn cùng số tiền | Không cộng/ghép; chọn đúng vai trò, không lấy phần tử đầu tiên tùy thứ tự. |
| Không có tổng hoặc OCR rác | Giữ khả năng abstain; không tăng coverage bằng số ngẫu nhiên. |

Không giữ model vô điều kiện và không bắt mọi lựa chọn phải khớp role regex.
Nếu cho phép giữ một ứng viên chưa chắc, biểu diễn needs_review và lý do trong
audit theo policy nhất quán. Public JSON không được dùng giá trị không parse
được hoặc không có nguồn để tránh null.

Rà soát các điểm yếu hiện có: `role()` first-match làm mất tín hiệu mâu thuẫn;
set role từ một kết quả khiến nhánh conflicting_labels khó có ý nghĩa; chọn
`totals[0]`; mặc định subtotal là tổng vì không thấy điều chỉnh; số âm/None trong
tập tiền; cùng số tiền nhưng khác nguồn; nhãn đã ghép nhưng guard đọc fragment.
Không biến việc “OCR không thấy dòng giảm/thuế” thành bằng chứng chắc chắn là
không có điều chỉnh khi vùng OCR đang thiếu/hỏng.

### 5.3. Kiểm tra thanh toán chỉ áp dụng khi đúng quan hệ

- Cash/change check cần xác nhận cùng nhóm giao dịch, vai trò, giá trị và độ
  tin cậy liên kết. Xét đặt cọc, nợ, hoàn tiền, split payment, cash + card.
- Phân biệt mâu thuẫn mạnh cần reject với thiếu bằng chứng hoặc số thừa OCR
  sai chỉ cần review. Không so bằng số học tuyệt đối với dữ liệu không chắc.
- Không cộng hai dòng cùng chỉ một khoản tiền, không coi khoản cash đã dùng
  trả hóa đơn là cash tendered. Ngưỡng/tolerance nếu có phải theo đơn vị và
  chính sách làm tròn rõ, không đặt mức riêng cho một bill.
- Số học chỉ dùng kiểm tra, không suy ra giá trị tiền thiếu để điền output.
  Lưu raw model, raw resolved fields, final fields và mọi quyết định rule/repair.

## 6. Tối ưu có đo lường

Ưu tiên thiết kế nhỏ, dễ đọc: module parse tiền, parse datetime, quan hệ, quyết
định; giữ public entry points khi hợp lý. Dùng constant/config có tên cho ngưỡng,
dataclass/typed structure nếu giúp loại trạng thái không hợp lệ. Không xây một
hệ plugin hoặc rules engine lớn chỉ để xử lý vài dạng chứng từ.

Precompute geometry, hướng dòng, normalized text và row/column context một lần
mỗi receipt. Hiện quan hệ lặp tính page slope/quét vùng cho từng số; tránh lặp
công việc đó, nhưng chỉ thêm index/cache nếu có lợi rõ và không làm sai mapping.
Giữ giới hạn thời gian/kích thước input, regex không backtracking bùng nổ; test
với chuỗi OCR dài/lỗi. Cache theo receipt, không rò trạng thái giữa ảnh.

Đo trước/sau thời gian parser/relations/guard trên cùng input, số candidates,
payload tokens và thời gian model tách khỏi thời gian load. Ghi p50/p95 kèm số
mẫu, phần warm-up nếu dùng; không tuyên bố nhanh hơn chỉ từ một lượt. Không cắt
candidate đúng để giảm token. Mặc định giữ một request Qwen/ảnh; retry chỉ khi
có lý do, giới hạn và audit. Không tăng context hoặc chạy GPU song song tùy ý.

## 7. Kiểm thử bao phủ và chống học thuộc mẫu

Thêm tests nhỏ theo contract, không chỉ dựng label_evidence đã đúng. Bao gồm
chuỗi OCR/polygon → candidates → payload/selection → guard → normalized output.

- Ma trận tiền: `35000`, `35 000`, NBSP/narrow NBSP, `35.000`, `35,000`, tiền
  gắn đơn vị, `.00`/`,00`, phần lẻ không hỗ trợ, âm/zero, grouping lỗi; nhiều
  số/cột/line, số lượng + tiền, tiền lặp ba lần, barcode/phone/invoice ID.
- Ma trận thời gian: DMY `/-.`, ISO, HH:mm/HH.mm/seconds, thiếu ngày/giờ,
  00:00/08:00, năm nhuận, ngày/giờ invalid, hai ngày cùng dòng, expiry/print,
  ngày giờ cạnh mã GD, date/time khác region và nhiều cặp gần nhau.
- Cùng nhãn “Thành tiền” trong item row và khu tổng; “Thanh toán” so với đã
  thanh toán/sau đặt cọc; subtotal/discount/tax, free/refund, nhiều phương thức.
- Quan hệ nhãn nguyên dòng/tách fragment, số trước nhãn, ảnh nghiêng, nhiều
  cột, hàng sát nhau, multi-label trong cùng region. Ghép fragment không làm
  mất tín hiệu discount hoặc lan nhãn sang hàng bên cạnh.
- Guard: raw đúng bị rule chặn; raw sai được sửa khi có căn cứ; conflict mạnh
  vẫn null; unknown không tự fail; schema/ID/span sai; thiếu hoặc partial OCR.
- Unicode offsets, số trùng giá trị khác vai trò, không bịa/double tiền,
  normalize/extract nhất quán, idempotence với input chuẩn nếu API hỗ trợ.

Thêm biến thể/property tests có seed: đổi tên cửa hàng và ID, đổi số tiền/ngày
hợp lệ nhất quán, hoán đổi thứ tự OCR, scale/translate, tách/gộp vùng chữ tương
đương, thêm hàng không liên quan. Đáp án ngữ nghĩa phải ổn định; candidate IDs
có thể đổi. Các biến thể này là test tổng quát, không được gắn đáp án qua ID.

Thêm counterexamples cho mọi rule mới: giữ “Thành tiền” tổng thì vẫn loại
“Thành tiền” hàng sản phẩm; nhận `08.29` là giờ thì vẫn không nhận giá 08.29
hoặc SKU tương tự làm giờ; ghép `35 000` thì không ghép quantity và price.
Chạy tests tái hiện trước sửa, tests liên quan, toàn bộ regression và lint.
Không xóa hoặc nới assertion cho xanh nếu chưa giải thích thay đổi contract.

## 8. Audit đáng tin cậy, tách hiệu quả parser và model

Sửa/hoàn thiện evaluator khi cần để dùng manifest và expected sidecar tùy chọn.
Bill_01/bill_02 có manifest `regions: []`; tạo expected review từ ảnh trong
sidecar chỉ cho evaluator, không chép GT vào input model. Không sửa audit JSON
thủ công sau chạy để làm số liệu đúng; report và summary phải sinh lại được.

- Đóng băng expected trước lượt đánh giá sau sửa, ghi nguồn review/annotation
  và field không chấm được. Không dùng prediction để tạo expected.
- Evaluator không gọi parser sản phẩm làm oracle. Chấm đúng giá trị và đúng
  nguồn/vai trò riêng: chọn giá sản phẩm bằng tổng không tự được tính đúng nguồn.
- Duyệt manifest đủ ảnh, giữ failed/missing/null trong mẫu số khi có expected;
  thiếu annotation không mặc nhiên đúng. Runtime thành công không là extraction đúng.
- Đánh giá datetime theo component + precision, không cắt `:00` tùy tiện làm
  giờ HH:00 sai. Nếu sửa metric, chấm lại cả baseline và sau với cùng policy.
- Không chuẩn hóa baseline raw bằng parser mới rồi gọi là baseline cũ. Dùng
  raw_fields đã lưu hoặc snapshot parser cũ; ghi riêng nếu không tái hiện được.
- Audit OCR → token → candidate → payload → raw Qwen → final: mất đáp án ở tầng
  nào, source đúng có còn không, model đổi hay rule đổi; tiền và datetime riêng.

Chạy hai lớp so sánh:

1. **Replay offline** trên cùng OCR và selection cũ, remap bằng source ID +
   spans, không bằng candidate ID hay số tiền. Nếu token mới gộp/tách làm không
   ánh xạ 1-1, ghi unmappable với lý do, không âm thầm đổi thành null rồi tính
   là lỗi model. Lựa chọn datetime cũ null vì không có candidates không tự
   chứng minh model mới sẽ chọn đúng; báo parser coverage và CUDA riêng.
2. **Qwen CUDA thật trên đủ 17 ảnh**, cùng OCR cache, model/hash/config và thứ
   tự ảnh. So với baseline gần nhất. Lưu đầy đủ requests/responses/candidates,
   raw/final, runtime và errors. Mỗi thay đổi code ảnh hưởng inference cần
   lượt xác minh phù hợp; chốt code trước lượt cuối, không sửa logic trong lúc
   batch đang chạy. Không chọn lượt đẹp nhất để báo.

Báo tối thiểu: accuracy raw/final, số có kết quả, sai nhưng có kết quả, raw đúng
bị guard làm sai/null, raw sai được sửa đúng, candidate recall theo giá trị và
nguồn, đáp án bị loại ở từng tầng, số needs_review/invalid/ambiguous, latency.
Phân biệt OCR, parsing, relations/role, Qwen, guard, normalization và GT/policy.

Sau khi ổn định, chọn **10 ảnh mới chưa dùng** bằng manifest/seed/checksum trước
khi xem kết quả, chạy đánh giá mở rộng một lượt. Dataset validation ở
`data/mcocr/val_images/val_images`; kiểm tra ảnh đã dùng trước đó và quyền có
nhãn, không gọi tên thư mục là bằng chứng ảnh chưa từng dùng. Review expected
độc lập nếu thiếu GT, không loại ảnh khó để làm đẹp chỉ số. Nếu dùng tập này
để sửa tiếp, đổi nhãn đánh giá thành dev; không tiếp tục gọi nó holdout.

## 9. Runtime, artifacts và bàn giao

- Giữ model/config hiện có (Q4_K_M; không gọi là BF16). Một server CUDA, một
  request tại một thời điểm; giải phóng OCR trước Qwen nếu chạy OCR mới.
  Kiểm tra RAM/VRAM, runtime offload và context thật; không CPU fallback ngầm.
- Giữ model ở máy nếu hash đúng, không tải lại. Cleanup đúng tiến trình tạo
  trong task; không kill app người dùng. Nếu thiếu tài nguyên/quyền/mạng, ghi
  rõ bước bị chặn và hoàn tất phần độc lập, không giả lập kết quả GPU.
- So sánh extraction chính dùng OCR cache. Chạy thêm smoke CLI một ảnh thật
  qua OCR → Qwen → JSON bốn field trong output mới; ghi rõ OCR mới có thể đổi.
  Cần lưu stderr/log riêng, stdout chỉ JSON khi thành công; lỗi runtime có
  exit code khác 0, không trả all-null như một lần xử lý thành công.
- Artifacts gồm snapshot/hashes, manifests/expected sidecar, OCR, candidate
  traces/relations, raw/final, reasons, tests/lint, runtime/performance, audit,
  report và demo HTML có link OCR JSON, JSON bốn field, JSON chẩn đoán.
- Giao diện không thêm phần đối chiếu ảnh đã bỏ. Confidence OCR ghi đúng ý
  nghĩa. Kiểm tra link và JSON schema; nêu rõ nếu chưa QA bằng browser.
- Sau xác minh có thể cập nhật `outputs/bill_02.json` từ kết quả pipeline thật,
  lưu bản trước sửa. Không điền expected bằng tay. Giữ bill_01 đúng 6000.
- Cập nhật `docs/QWEN_DEMO.md` với lệnh tái hiện đã kiểm tra.

Tiêu chí bàn giao: bill_02 trả đúng **35000** và **2020-09-30T08:29** với source
spans đúng; bill_01 và các đáp án đúng trước đó được giữ; không tăng tiền sai
được chấp nhận để giảm null; các ca OCR thiếu giữ xử lý rõ ràng. Mọi thay đổi
ở seller_name/address phải được review, không bỏ qua vì đang tập trung parser.

Báo cáo cuối bằng tiếng Việt, link demo/JSON/report, bảng đủ 17 ảnh và kết quả
tập mới tách riêng; raw/final trước/sau, regression, false rejection/acceptance,
candidate bị mất, test/lint/GPU, độ trễ và phần chưa xác minh. Không tuyên bố
“tổng quát mọi hóa đơn”, “tối ưu nhất” hoặc “chỉ còn lỗi OCR” từ vài ảnh.
Nếu còn yêu cầu chưa đạt, nêu chính xác; chỉ kết luận trong phạm vi đã kiểm chứng.
