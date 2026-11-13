# Rà soát và sửa total_amount, kiểm soát regression trên OCR → Qwen

Bạn là kỹ sư Python phụ trách DocuCheck-AI. Hãy đọc repository và artifacts thực tế,
triển khai sửa lỗi, chạy kiểm thử, audit trước/sau và demo Qwen CUDA thật.
Không chỉ lập kế hoạch, đổi prompt hoặc trả lại hướng dẫn để người dùng tự làm.

Mục tiêu: sửa lỗi liên kết nhãn–giá trị, phân loại vai trò tiền và hậu xử lý đang
loại nhầm đáp án đúng. Không tăng số field có kết quả bằng cách giữ lại tiền sai.
Thiết kế tổng quát, có bằng chứng và kiểm thử; không vá theo tên cửa hàng, image_id,
candidate ID, số tiền hay vị trí cố định của một hóa đơn.

## 1. Giữ contract và định nghĩa nghiệp vụ

- Giữ nguyên bốn key: `seller_name`, `seller_address`, `transaction_datetime`,
  `total_amount`. Không đổi key `total_amount` thành `invoice_total`.
- `total_amount` vẫn là tổng giá trị cuối hóa đơn sau giảm giá/thuế/phí được ghi
  trên chứng từ, trước khấu trừ đặt cọc/đã trả để tính dư nợ. Quyết định này đã
  được người dùng chốt; không tự chuyển thành tiền khách đưa hay số còn phải trả.
- Nhãn trên chứng từ không bắt buộc phải chứa chính xác chữ “Tổng hóa đơn”.
  “Khách phải trả”, “Tổng thanh toán”, “Tổng số tiền thanh toán” hoặc nhãn khác
  có thể chỉ tổng cuối; phải xét ngữ cảnh, không dùng danh sách từ khóa như điều
  kiện bắt buộc duy nhất. “Phải trả sau đặt cọc” có thể là số còn lại.
- `invoice_total` chỉ là vai trò nội bộ. UI cần thấy rõ `total_amount` cùng diễn
  giải tiếng Việt; không để người dùng tưởng hệ thống đã đổi field nghiệp vụ.
- Giữ value spans chính xác, OCR nguyên bản, provenance và lựa chọn gốc của model.
  Không nối/cộng nhiều số tiền thành một giá trị. Không bịa số khi OCR thiếu.
- Giữ model Qwen3-4B-Instruct-2507 Q4_K_M, revision/hash và runtime hiện có.
  Không đổi model, fine-tune hay thay OCR backend để né lỗi ở bộ chọn/hậu xử lý.
- Phạm vi sửa chính là tiền. Audit regression cả tên, địa chỉ, ngày giờ; không
  mở rộng viết lại ba bộ trích xuất đó nếu không cần cho thay đổi dùng chung.

## 2. Đọc code, chụp baseline trước mọi thay đổi

Đọc AGENTS.md nếu có, kiểm tra git status. Code Qwen hiện có nhiều file untracked:
phải giữ nguyên công việc của người dùng; không git reset/clean hoặc xóa artifacts.

Đọc tối thiểu:

- `src/docucheck/extraction/candidates.py`, `invoice_total.py`, `qwen.py`.
- `scripts/demo_ocr_qwen.py`, `extract_receipt_fields.py`, `run_ocr_cuda.py`.
- `scripts/evaluate_qwen_demo.py`, `audit_invoice_total_demo.py`,
  `prepare_qwen_test_batch.py`.
- `tests/test_qwen_candidates.py`, `test_invoice_total.py`, `test_qwen_extraction.py`.
- `configs/qwen3_4b_q4_k_m.json`, `docs/QWEN_DEMO.md` và prompt sửa tiền trước đó.

Tập hồi quy bắt buộc gồm đủ 15 ảnh, kiểm tra trùng bằng image_id và checksum:

1. Hai ảnh ở `outputs/ocr_to_qwen/invoice_total_fix/run_20261113/old_v2/`.
2. Ba ảnh ở `outputs/ocr_to_qwen/invoice_total_fix/run_20261113/new_v2/`.
3. Mười ảnh ở `outputs/ocr_to_qwen/test_10_20261113_ready/batch_01/` đến `batch_04/`.

Lưu snapshot code, prompt, config, manifest, hash OCR và nguồn baseline vào thư
mục run mới trước sửa. Giữ nguyên outputs cũ. Xác minh mỗi run đã dùng code/config
nào; nếu không truy được provenance thì ghi chưa xác minh, không mặc nhiên coi
code hiện tại chính là code đã tạo mọi kết quả cũ.

## 3. Những phát hiện cần tái hiện và truy nguyên

Tại thời điểm viết prompt, cả 10 ảnh mới đều có `total_amount = null` sau guard:
6 trường hợp `conflicting_invoice_totals`, 4 trường hợp `invoice_total_not_unambiguous`.
Đây là số liệu từ JSON đã lưu, chưa phải kết luận cả 10 lần chặn đều sai.
Tái kiểm tra nếu artifacts đã thay đổi. Không dùng `status: ok` của request để
kết luận bốn field đúng hoặc đầy đủ.

| Ảnh | Bằng chứng đã đọc | Vấn đề cần xử lý/audit |
|---|---|---|
| `0bec335000fe061b7d5beead` | Qwen chọn M023 = 190.000; guard xóa thành null. M019–M022 mang các số 2, 26.000, 0, 6 nhưng bị gán `invoice_total` cùng M023. | Nhãn “Tổng cộng” bị nối sang hàng hàng hóa và cột số lượng, sinh xung đột giả. |
| `adce2f6bba6285916eee285e` | Qwen chọn M007 = 40.000; guard xóa. M008 = 0 dính cả nhãn tổng và “TỔNG TIẾN Ã GIẢM”. | Nhãn dòng kế bị lan; OCR lỗi nhãn giảm giá bị regex “tổng tiền” nhận sai vai trò. |
| `1b4f9e96ca489a058e41d461` | OCR chủ yếu là ký tự/số rời; Qwen chọn M016 = 1. GT ghi 42.600 nhưng chuỗi tiền đúng không có trong OCR đã lưu. | Chặn đáp án 1 là hợp lý. Xem ảnh gốc để chẩn đoán OCR; không lấy GT điền vào kết quả. Chưa có bằng chứng xác nhận lỗi xoay ảnh. |
| `3ed70d250e4d69648ea1b179` | Qwen chọn 164.000, nhãn “Khách phải trả”, role unknown rồi bị chặn. | Regex thiếu cách diễn đạt; cần xác nhận vai trò bằng ngữ cảnh chứng từ. |
| `451eab979381fbf5c38decee`, `daba809a92808753fe0cdff5` | Qwen chọn 49.500 và 151.825; tiền giảm 0/8.100 bị gán tổng, dẫn tới null. | Kiểm tra cùng họ lỗi nhãn giảm giá và liên kết hàng. |
| `19705196bc7942cf19ea54ea` | Qwen chọn 184.500; số 0 bị nối sang nhãn tổng, gây null. | Ngăn lan nhãn ngay cả khi OCR nhãn dòng cạnh hỏng nặng. |
| `23f7f7d5a151f877ee95fab1` | GT ghi “Tong so tien thanh toan:” và `27,200.00`; model chọn 2, role tax_fee. | Audit OCR → parser → candidates → payload; chưa khẳng định tiền đúng có trong OCR. Có nguy cơ bỏ mất tiền vì định dạng phần thập phân. |
| `3bfe5923d44b0bde3892ebfc` | Qwen chọn 22.300 cạnh “Cộng tiền hàng”; GT text là `22,300 22,300`. | Audit ảnh và nghiệp vụ, không mặc định mọi “tiền hàng” đều là tổng cuối. GT lặp số không được ghép thành số mới. |
| `da51b171c389944c0a4e98ee` | Qwen chọn OCR `9,132,000`, GT ghi 132.000; 500.000 khách trả cũng bị gán tổng. | Tách lỗi chữ số OCR khỏi lỗi quan hệ. Không cắt số 9 hay lấy 132.000 chỉ để khớp GT. |

Các ID trên chỉ là tọa độ tra cứu của baseline, không phải quy tắc production.
Sau thay đổi candidate IDs có thể đổi: so sánh qua source ID + exact span + vai
trò, không nối trước/sau chỉ bằng tên M007/M023 hoặc cùng một số tiền.

## 4. Sửa đúng tầng nguyên nhân

### 4.1. Quan hệ nhãn–giá trị phải có bằng chứng

Hiện `build()` liên kết gần như mọi vùng bên trái có overlap chiều dọc > 25%
chiều cao nhỏ hơn. Đây không đủ để khẳng định cùng hàng, đặc biệt ảnh nghiêng.

Thay bằng cơ chế nhỏ, có thể giải thích và kiểm thử:

- Xét tâm/baseline hàng, chiều cao chữ, khoảng cách tương đối, polygon và hướng
  dòng khi có; phân biệt hàng và cột. Không chỉ tăng một ngưỡng overlap.
- Xét nhãn cùng region và khác region; số có thể nằm trái hoặc phải nhãn.
  Khi một region chứa nhiều nhãn/số, liên kết theo span/cụm lân cận, không lấy
  toàn bộ text làm nhãn chung cho mọi số.
- Phân biệt cột số lượng/đơn giá/thành tiền, hàng sản phẩm và khu tổng kết bằng
  bằng chứng bố cục/ngữ nghĩa. Không loại số nhỏ hoặc số 0 chỉ theo giá trị.
- Mỗi quan hệ giữ nguồn nhãn, span, hướng, khoảng cách chuẩn hóa, lý do chọn,
  dấu hiệu phản đối và mức hỗ trợ. Quan hệ yếu chỉ là ngữ cảnh, không đủ để
  tạo thêm một “tổng được xác nhận” và phủ quyết lựa chọn tốt.
- Giữ các phương án mơ hồ trong audit; không xóa đáp án đúng để ép model.
  Nếu lọc khỏi payload, lưu lý do và đo candidate recall trước/sau.
- Giữ source text nguyên bản. Chuẩn hóa để so khớp ở trường riêng. Không gọi
  điểm heuristic của quan hệ là xác suất model đúng.

### 4.2. Vai trò tiền dựa trên cả cụm nhãn và ngữ cảnh

Giữ phân biệt invoice_total, subtotal, discount, tax_fee, deposit, paid_amount,
tendered_amount, balance_due, change, unknown; có thể thêm trạng thái mơ hồ nội bộ.

- Nhãn cụ thể có giá trị hơn từ “tổng” chung chung. “TỔNG TIỀN Ã GIẢM” phải có
  bằng chứng discount/unknown, không thành invoice_total chỉ vì chứa “tổng tiền”.
- Hỗ trợ lỗi dấu/khoảng trắng/viết tắt hoặc thiếu ký tự có giới hạn, kèm bằng
  chứng và kiểm thử âm tính. Không fuzzy-match rộng để mọi nhãn hỏng đều là tổng.
- Không blacklist tuyệt đối “Khách phải trả”, “Tiền khách trả”, “Cộng tiền hàng”.
  Xét chứng từ: tiền khách đưa 500.000 có thể khác tổng 132.000; tiền hàng có
  thể là subtotal khi còn giảm giá/thuế, hoặc trùng tổng cuối ở hóa đơn đơn giản.
- `unknown` nghĩa là rule chưa đủ kết luận, không tự động nghĩa là model sai.
  Cho phép lựa chọn có bằng chứng đủ tốt dù không khớp một keyword cố định.

### 4.3. Guard không được biến xung đột giả thành mất đáp án

Viết decision policy rõ trước khi code, thể hiện tối thiểu:

| Tình huống | Hành vi cần đạt |
|---|---|
| Model chọn tổng có bằng chứng tốt; đối thủ chỉ có liên kết yếu/sai hàng/số lượng/giảm giá | Giữ lựa chọn có căn cứ; không null vì đối thủ yếu. |
| Model chọn paid/deposit/change nhưng có một tổng cuối rõ ràng | Có thể sửa theo rule; lưu nguyên raw choice và lý do. |
| Nhiều ứng viên cùng số | Không ghép/cộng số; vẫn chọn đúng nguồn/vai trò. Cùng giá trị không tự chứng minh đúng vai trò. |
| Hai tổng khác nhau đều có bằng chứng mạnh, chưa phân biệt tổng trước/sau thuế/giảm | needs_review/null, không chọn max hay giữ model vô điều kiện. |
| Nhãn lạ nhưng ngữ cảnh tổng cuối đủ rõ | Không từ chối chỉ vì role unknown; ghi căn cứ giữ/chọn. |
| OCR chỉ có rác, giá trị không có nguồn hoặc không đủ bằng chứng | needs_review/null có lý do; không lấy số ngẫu nhiên để lấp ô. |

Không sửa bằng cách tắt guard, luôn tin Qwen, chọn số lớn nhất/cuối cùng, giữ
duy nhất một keyword hay cộng các dòng thanh toán để suy ra tiền thiếu.
Tính toán, nếu có, chỉ kiểm tra tính nhất quán; trong phạm vi này kết quả phải
truy được về giá trị tiền hiện diện trong OCR, không tự tạo giá trị mới.

Lưu raw_model_selection, raw resolved value, final_selection, final resolved
value, decision_source, reason và các bằng chứng chấp nhận/bác bỏ. Nếu có retry
model thì giới hạn số lượt, lưu từng request/response và báo chi phí/thời gian.
Không cần thêm một vòng LLM chỉ để thay lỗi rule bằng lỗi model khác.

### 4.4. Parser tiền không tạo lỗi mới

Audit regex tạo candidate và normalize cùng nhau. Trường hợp rõ như `27,200.00`
không được cắt thành 27 hay 200. Giữ raw span, phân biệt dấu nghìn/dấu thập phân
bằng chính sách format có kiểm thử; dùng Decimal nếu cần, tránh float cho tiền.
Với phần lẻ bằng 0 có thể chuẩn hóa về integer tương thích contract; phần lẻ
khác 0 hoặc format thực sự mơ hồ phải được biểu diễn/báo rõ, không làm tròn ngầm.

Bảo toàn `0`, số âm/hoàn tiền, tiền lặp ở nhiều dòng, tiền nhiều số trong một
region. Không loại theo confidence thấp đơn lẻ. `1111,990` không tự sửa thành
111.990; `9,132,000` không tự sửa thành 132.000. Phân biệt số tiền thực với số GD,
ngày, số điện thoại, mã hàng và số lượng bằng ngữ cảnh và exact spans.

## 5. Kiểm thử chống sửa chỗ này hỏng chỗ khác

Viết regression test tái hiện lỗi trước khi sửa; test mới phải chứng minh thất
bại trên baseline tương ứng. Tách test tiền/quan hệ/guard khỏi network và model.
Không chỉ dựng `label_evidence` đã đúng rồi coi là đã test việc ghép nhãn.

Nhóm kiểm thử bắt buộc:

1. Từ OCR polygon/text qua build → roles → guard → resolve: hàng tổng nằm sát
   hàng hàng hóa; cùng hàng có cả số lượng và tiền; receipt nghiêng, lệch hàng,
   nhãn bên phải; nhãn và nhiều số nằm chung region.
2. Tổng đúng cạnh giảm giá bằng 0/khác 0 và nhãn OCR mất “Đ”; đối thủ yếu không
   làm mất tổng. Hai tổng mạnh mâu thuẫn vẫn bị chặn; không xóa khả năng abstain.
3. “Khách phải trả”, “Tổng số tiền thanh toán”, “Cộng tiền hàng” có/không có thuế,
   giảm giá, đặt cọc. Bao gồm ví dụ âm tính “phải trả sau đặt cọc”.
4. Tổng 840.000 / đã trả 300.000 / còn 540.000; tổng 78.000 / khách đưa 100.000 /
   thừa 22.000; subtotal 120.000 / giảm 20.000 / tổng 100.000; thanh toán nhiều
   phương thức; ba dòng trùng tiền nhưng khác vai trò. Không hard-code số mẫu.
5. Format tiền rõ/mơ hồ, decimal, zero, negative, grouping lỗi, số liền mã GD;
   không lấy một phần số lỗi làm tiền khác, không ghép GT hoặc OCR lặp số.
6. Biến thể hình học và nội dung trên cùng fixture: đổi thứ tự OCR, scale/translate
   đồng nhất, đổi số tiền nhất quán, thêm hàng không liên quan, thêm quan hệ yếu.
   So sánh lựa chọn ngữ nghĩa/source spans, không bắt ID đánh số giữ nguyên.
7. Candidate đúng có OCR confidence thấp; candidate sai confidence cao; không
   dùng điểm OCR thay cho độ đúng vai trò.
8. Dữ liệu thiếu/rác; invalid ID, sai schema, timeout, context overflow, response
   bị cắt; không success giả. Replay raw model đúng và raw model sai đều được test.
9. Regression ba field khác: tên không lặp ghép, địa chỉ giữ đủ dòng, ngày giờ
   loại số GD và giữ đúng độ chính xác phút/giây. Bao gồm giờ HH:00 khi audit.

Thêm fixture trích từ các lỗi thật với nguồn/hash và expected được review độc
lập, cùng fixture tổng quát để tránh học thuộc bộ ảnh. Giữ test cũ hoặc giải
thích rõ contract thay đổi nếu buộc phải sửa assertion; không xóa test đang đỏ.
Chạy test liên quan rồi toàn bộ regression phù hợp, lint các file thay đổi.

## 6. Đánh giá phải tách rule, model, OCR và annotation

Tạo evaluator/audit dùng được cho manifest tùy chọn; script audit tiền cũ chỉ
có reference của 5 ảnh, không dùng nguyên nó để chấm 10 ảnh mới.

- Giữ GT gốc, tách expected phục vụ nghiệp vụ và ghi lý do khi khác annotation.
  Đọc ảnh gốc khi tiền/nhãn mơ hồ. Không suy ra expected từ prediction.
- Không dùng chính parser/guard production làm nguồn duy nhất để tạo đáp án
  chấm. Nhãn lặp `22,300 22,300` cần review và lưu provenance, không tự ghép số.
- GT/expected chỉ đi vào evaluator sau inference, không vào builder, prompt,
  guard, retry hay lựa chọn OCR. Không tối ưu rule bằng image_id/merchant.
- So cùng một policy đánh giá trên trước và sau. Nếu sửa evaluator (ví dụ
  lỗi bỏ `:00` làm sai HH:00, thiếu prediction khỏi mẫu số, report hard-code hai
  ảnh), chấm lại cả hai bên và tách thay đổi metric khỏi thay đổi extraction.
- Tính riêng raw Qwen accuracy, final accuracy, tỷ lệ có giá trị, số sai nhưng
  vẫn có giá trị, số raw đúng bị guard làm sai/null, số raw sai được sửa đúng,
  candidate recall và đáp án mất ở từng tầng. Null không phải đáp án đúng khi
  GT có tiền; trường hợp OCR thiếu vẫn là lỗi end-to-end dù abstain là hợp lý.
- Phân loại từng lỗi: OCR thiếu/sai chữ số; parser; liên kết/role; lọc candidate;
  Qwen chọn sai; guard hại đáp án; normalization; annotation/policy conflict.
  Kiểm tra khả năng có nhiều nguyên nhân trên một ảnh.

Thực hiện hai phép so sánh:

**A. Replay offline:** dùng cùng OCR và raw selection đã lưu để đo riêng tác
động parser/relations/guard. Khi ID thay đổi, remap bằng source spans và kiểm
tra uniqueness; không map chỉ bằng số tiền. Không gọi replay là model mới chạy.

**B. Model thật:** chạy Qwen CUDA sau sửa trên cùng OCR cache của đủ 15 ảnh,
so với raw/final baseline đã lưu. Giữ model, generation config và thứ tự ảnh;
lưu prompt/payload mới. Nếu baseline không đủ tin cậy để so, chạy lại baseline
đã snapshot riêng, không thay đổi artifacts cũ. Báo mọi lượt, không chọn lượt
đẹp nhất. Mọi regression phải điều tra, sửa và kiểm lại nhóm chịu ảnh hưởng.

Sau khi ổn định tập 15 ảnh, nếu có dữ liệu chưa dùng, cố định thêm 5 ảnh qua
manifest/seed/checksum trước khi xem nhãn và chạy kiểm tra mở rộng một lượt.
Không chọn ảnh dễ. Nếu dùng kết quả đó để chỉnh rule tiếp, đánh dấu chúng đã
thành dev, không tuyên bố là holdout độc lập. Nếu chưa chạy, ghi chưa xác minh.

## 7. Demo GPU và artifacts

- Chạy tuần tự, một server/request; CLI hiện giới hạn 3 ảnh/batch thì chia batch.
  Xác minh VRAM/RAM trước khi chạy, CUDA offload từ runtime log; không CPU fallback,
  không nạp OCR và Qwen cùng lúc, không kill ứng dụng khác. Dừng đúng server mình tạo.
- Dùng model và môi trường sẵn có, không tải lại nếu hash đúng. Context/token
  preflight phải cùng config server/client; không cắt âm thầm candidate đúng.
  Sửa hướng dẫn còn `-c 4096` nếu runtime dùng 8192; kiểm tra cấu hình thực tế.
- So sánh chính dùng OCR cache và ghi rõ `ocr_reused`. Nếu thử OCR lại ca bị rác,
  lưu thành experiment riêng, ghi transform nếu có, không trộn vào số liệu
  chứng minh hiệu quả sửa extraction trên cùng OCR.
- Tạo `outputs/ocr_to_qwen/total_amount_audit_fix/<run_id>/` chứa snapshot,
  manifest, OCR/provenance/hash, input, candidates/relations/roles, payload,
  response, raw/final, decision log, runtime, audit JSON, report và trang demo.
- Demo giữ bốn field, confidence OCR ghi đúng ý nghĩa, trạng thái và lý do ngắn
  khi trống; link JSON OCR/kết quả/audit. Không biến số field trả về thành số
  field chính xác; không ghi “4/4 đúng” chỉ vì schema có đủ bốn key.
- Không khôi phục phần đối chiếu ảnh trên giao diện người dùng đã yêu cầu bỏ.
  Có thể dùng ảnh gốc nội bộ để audit và giữ link ảnh. Kiểm tra HTML/link và
  giao diện nếu có công cụ; phần chưa xem trực quan phải báo rõ.

## 8. Tiêu chí bàn giao

Không tuyên bố “không bao giờ regression”. Chỉ báo không phát hiện regression
trên tập/kiểm thử đã thực sự chạy, nêu kích thước và giới hạn của chúng.

Để đánh dấu hoàn tất phần sửa extraction:

- Hai ca 190.000 và 40.000 có nguồn đúng phải không còn bị guard loại do quan
  hệ yếu/sai hàng; các ca cùng họ được kiểm chứng, không chỉ sửa riêng batch 1.
- Năm ảnh baseline giữ đúng total_amount: 90.996, 1.300.000, 108.000, 111.990,
  101.100 (đối chiếu image_id trong report baseline, không dựa thứ tự liệt kê).
- Không tạo giá trị giả cho ảnh thiếu OCR; các trường hợp xung đột thật vẫn
  xử lý đúng. Không chuyển lỗi null thành tiền sai để làm đẹp coverage.
- Không phát sinh regression chưa giải thích ở ba field khác hoặc làm mất
  đáp án đúng trong candidates/payload. Nếu còn lỗi, báo chưa đạt tiêu chí tương ứng.
- Có kiểm thử tái hiện lỗi, regression, lint, replay và kết quả CUDA thật;
  mỗi claim về cải thiện đều truy được artifacts. Lỗi OCR tồn tại được tách
  rõ khỏi phần đã sửa, không che đi hoặc dùng GT lấp kết quả.

Phản hồi cuối bằng tiếng Việt: tóm tắt nguyên nhân và code thay đổi; link demo,
OCR JSON, kết quả và report; bảng đủ 15 ảnh gồm expected, raw/final trước/sau,
vai trò/bằng chứng, decision_source và lỗi còn lại. Báo số đáp án bị lọc mất,
số guard hại/sửa đúng, regression, test/lint/GPU và phần chưa xác minh.
Cập nhật `docs/QWEN_DEMO.md` bằng lệnh PowerShell chạy lại đã kiểm tra.
