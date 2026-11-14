# Rà soát mức sẵn sàng MVP — 15/11/2026

## Kết luận và phạm vi

Đã có demo kỹ thuật chạy end-to-end trên máy hiện tại: ảnh → PHOCR/VietOCR E1
CUDA → Qwen → JSON bốn field, HTML, bằng chứng và diagnostics. Chưa đủ cơ sở
nghiệm thu toàn bộ MVP theo `docs/idea.md`: thiếu quy trình người dùng sửa/xác
nhận, chưa có kết quả kiểm chứng hệ thống cho bản hiện tại, còn lỗi chọn field.
Không yêu cầu accuracy 100%, đổi model hay hỗ trợ ngoài biên lai một trang để
hoàn thành MVP. Cần chốt tiêu chí chất lượng và chấp nhận lỗi có review.

Đây là audit đọc code và artifacts, không chạy test, replay, OCR, model hoặc
benchmark. Không sửa logic sản phẩm trong lượt audit. HEAD `168c1a7`; nhiều file
refined/adapter/test chưa commit hoặc chưa track, nên HEAD chưa tái tạo working tree.

## Bằng chứng các lượt người dùng đã chạy

Đọc bảy thư mục mới nhất dưới `outputs/ocr_to_qwen/single_receipt/`:

| Run | Nhận xét từ JSON/log đã lưu |
|---|---|
| `b1702825ab8f9751ccb08ba7_mp1334rw` | THỨC COFFEE; 22 Quang Trung, P10, Gò Vấp; 35000; ngày 2019-03-30, thiếu giờ |
| `d72897d5cbd21ef7271bc523_mchk2o1n` | Co.op; xuất bốn giá trị, tên/địa chỉ needs_review |
| `9cc6824f6807bcbb06eb7738_g9zdiunw` | Nhà sách; xuất bốn giá trị, địa chỉ uncertain_layout |
| `9739bab81677cc3caeec29e2_ir5x7xpb` | Năm Oánh; chỉ có ngày; tổng 107000 có semantic_conflict |
| `5954003af0730153bda97e5f_f80wswgh` | Vincommerce; chọn địa chỉ nhầm dòng chi nhánh; tổng 5800 |
| `efa83906c73cd08da651a934_jao2mtbd` | Joma; chọn địa chỉ quảng cáo footer; tổng 305000 |
| `3a6d119e42d7d56485e829e6_fht12484` | THỨC COFFEE và địa chỉ đầy đủ; thiếu giờ; tổng 35000 có uncertain_relation |

Cả bảy run: receipt status ok, schema 3.1-refined-text-ids, OCR scale 2;
ít nhất một field needs_review. Prompt 2255–6166 token, thêm reserve 512 nằm
trong context 8192 ở các run này. GPU memory peak được sampling trong runtime
5389–5906 MiB: là bộ nhớ GPU toàn máy tại các thời điểm lấy mẫu, không phải peak
chính xác của pipeline. Hai run Thức không được coi là hai ca độc lập để đo
chất lượng, dù hash ảnh khác nhau. Không dùng 7/7 chạy thành công làm accuracy.
Chưa đối chiếu toàn bộ bảy ảnh với reference đã khóa, chưa xác minh mọi field đúng.

## Phát hiện ưu tiên

### P1 — Địa chỉ đúng có trong OCR nhưng Qwen chọn sai chủ thể/phần địa chỉ

- Joma: OCR R005 `43 Tô Ngọc Vân ( West Lake)`. Model chọn R051/R052:
  `22 Ly Quoc Su 8 43 To Ngoc Van, 38 Lieu Giai Hanoi`, sau R050 `Enjoy Joma at`.
  Lỗi lựa chọn vẫn còn, không thể đổ cho OCR thiếu địa chỉ.
- VinCommerce: R002 `Số 590 Trần Phú, P. Cảm Thủy` đã có; model chọn R001
  `VM% anh 690 Trần Phú` và R004, bỏ R002. Có cả OCR sai chữ và model chọn sai.
- Thức trước cập nhật OCR từng kéo GÒY Vấp sang tên; hai run mới tên/địa chỉ đã
  cải thiện, chưa chứng minh lỗi cùng loại đã hết trên các bố cục khác.

Ưu tiên reference cho branch/header/footer, nhóm địa chỉ cùng chủ thể và review
chọn thiếu/thừa. Không tự chuyển token dựa vào tên thương hiệu hoặc từ khóa tỉnh.

### P1 — Trạng thái kỹ thuật chưa đủ bảo vệ người dùng cuối

`refined.py` trả receipt `status=ok` kể cả có field `invalid_evidence` hoặc
model_abstained; field status/`field_validation_failed` có nhưng public JSON
chỉ bốn giá trị. Đây là contract đã chọn, tuy nhiên downstream chỉ đọc JSON
sẽ bỏ mất cảnh báo. Guard tiền refined advisory-only, có thể giữ số OCR sai.
Baseline vẫn bật semantic guard cũ, có các vấn đề đã biết và vẫn là default.

Cần trạng thái review/confirmed ở lớp ứng dụng hoặc sidecar gắn rõ run/image,
không đổi JSON bốn field nếu nhóm vẫn cần contract đó. Người dùng phải thấy và
xác nhận các field đáng nghi; không coi confidence OCR là xác suất chọn đúng.

### P1 — File output cũ có thể bị nhầm thành kết quả lần chạy lỗi

`scripts/extract_receipt.py` chỉ viết `--output` sau pipeline thành công.
Nếu dùng lại `outputs/bill_refined.json` rồi run mới fail, file cũ vẫn còn.
CLI báo lỗi đúng nhưng ứng dụng/đồng đội mở file có thể xem nhầm bill trước.

Nên dùng output theo run/image và manifest kết quả, chỉ công bố đường dẫn khi
run thành công; đảm bảo consumer kiểm tra exit/status. Không tự xóa file cũ
của người dùng hoặc ghi null để che lỗi.

### P1 — Chưa đủ bằng chứng kiểm chứng/bàn giao bản hiện tại

Có workflow `.github/workflows/tests.yml` cho unit tests Ubuntu, nhưng không có
kết quả CI của working tree chưa commit; cũng chưa chạy test mới theo yêu cầu.
Demo trên máy hiện tại không xác minh fresh setup trên máy thành viên khác.
Chưa có đánh giá reference khóa trước, regression baseline/refined trên cùng
OCR E1 và nhóm ảnh mới độc lập. Các metrics OCR Tesseract trong README là lịch sử.

### P2 — Datetime bỏ giờ dù OCR đã nhận dạng

Run Thức có R022 `13.53` và R027 `13.52`. `candidates.py` nhánh nối giờ ở region
khác chỉ nhận dấu `:` và lấy kết quả đầu tiên gần theo y, chưa phân vai giờ
vào/giờ ra. `datetime_parser.times()` chỉ nhận giờ dấu chấm khi text có ngày.
Vì vậy có lỗi coverage của ứng viên, không chỉ lỗi chọn Qwen.

Cần hỗ trợ format dựa nhãn và quan hệ, có nhiều phương án khi có hai giờ; chốt
nghiệp vụ giờ thanh toán/giờ ra. Không mặc định lấy giờ đầu hay thêm 00:00.

### P2 — Mức review cao, chưa đo khả năng phân biệt đúng/sai

7/7 run có needs_review. Nhiều khối, nghiêng, gross total có thể tạo cảnh báo
dù giá trị đúng. Chưa chấm false alarm/false acceptance. Nếu người dùng phải
review mọi field thì giá trị tự động hóa giảm. Không sửa bằng cách tắt cảnh báo
đại trà; cần dữ liệu đối chiếu để chọn tín hiệu phù hợp.

### P2 — Giới hạn runtime và lỗi vận hành

- Managed server cố định port 8097, mỗi invocation nạp model lại; hai lần chạy
  đồng thời dễ tranh port/VRAM. Hỗ trợ MVP một tác vụ tại một thời điểm là đủ,
  nhưng cần thông báo hoặc khóa rõ ràng.
- `finally` dừng Qwen server; không có cleanup tương ứng cho extraction child
  nếu người dùng ngắt trong lúc chạy. OCR subprocess không có timeout tổng.
  Đây là rủi ro từ đọc code, chưa tái hiện hang/orphan trong lượt này.
- Runner dừng cả pipeline khi một OCR candidate fail, dù có thể còn đủ dữ liệu
  để trích xuất. Cần chính sách partial OCR rõ ràng; không coi partial là complete.
- Dữ liệu dài vẫn có thể vượt context/output budget; các run mới nhỏ chưa chứng
  minh khả năng xử lý bill dài. Có preflight và báo lỗi thay vì cắt âm thầm.
- `--reuse-ocr` kiểm tra profile trong managed demo; gọi trực tiếp
  `extract_receipt_fields.py --ocr ...` vẫn có thể dùng cache cũ. Có provenance,
  nhưng người vận hành cần hiểu đây là đường phục vụ đối chiếu lịch sử.

### P2 — UX và tài liệu chưa khép kín MVP

`docs/idea.md` yêu cầu rà soát/sửa/xác nhận và bằng chứng vùng ảnh. Hiện có JSON
source spans/polygons, HTML bảng kết quả/link ảnh, nhưng chưa có workflow sửa và
lưu kết quả confirmed hay click field để chỉ đúng vùng ảnh. Annotation plot
utilities không thay thế trải nghiệm review kết quả extraction. Không bắt buộc
FastAPI/Streamlit; chỉ cần một giao diện review nhỏ hoặc quy trình có lưu xác nhận.

README vẫn nói chưa triển khai OCR/extraction và hướng dẫn môi trường Tesseract.
`pyproject.toml` core extras Torch CPU là chủ ý, khác môi trường GPU riêng;
`docs/PIPELINE.md` có hướng dẫn GPU nhưng demo Windows hardcode `.venv-phocr-gpu`,
runtime llama b12345 và đường weights. Cần một hướng dẫn setup Windows thống nhất
và kiểm tra dependency/weights trước demo trên máy khác.

Renderer luôn link `report.md`, trong khi managed demo không tạo file đó: có
nguy cơ link hỏng trong run mới. Dữ liệu ảnh/OCR/raw response còn được lưu local
mỗi run; cần hướng dẫn vị trí và dọn dữ liệu khi giao người dùng khác.

## Checklist chốt MVP đề xuất

1. Chốt phạm vi “một ảnh biên lai → bốn field → người dùng kiểm tra/xác nhận →
   xuất JSON”; ghi rõ trường hợp chỉ có ngày và trường không đọc được.
2. Khóa code/config/OCR profile, chạy test hiện có và regression các lỗi đã gặp.
   Không promote refined chỉ dựa trên vài ví dụ dễ.
3. Review một tập cố định khoảng 20–30 ảnh đa dạng, có nhóm chưa dùng chỉnh rule;
   báo điểm từng field, tỷ lệ đúng cả bốn, thiếu/null, review và lỗi kỹ thuật.
   Đây là acceptance set nhỏ, không thay thế benchmark toàn dataset.
4. Hoàn thiện sửa/xác nhận và liên kết evidence tối thiểu; lỗi review được phép
   tồn tại nếu hiển thị rõ và người dùng sửa được. Chốt ngưỡng nghiệm thu trước đo.
5. Ngăn nhầm output cũ, xử lý busy/failure rõ, thống nhất setup Windows/GPU,
   cập nhật README, commit đủ code/test/config/docs sau khi kiểm chứng.

Không nằm trong blocker của MVP đã mô tả: danh sách mặt hàng, đa trang, kế toán,
phát hiện gian lận, fine-tune hay đổi model. Chưa tuyên bố hoàn tất sản phẩm
hoặc quality gate; hiện đủ demo kỹ thuật có người giám sát trên máy này.
