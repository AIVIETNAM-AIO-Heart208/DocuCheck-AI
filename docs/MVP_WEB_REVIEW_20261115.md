# Rà soát MVP web và Docker — 2026-11-15

Cập nhật sau review: đã sửa khóa form/chống gửi lưu lặp, bỏ phản hồi cũ khi đổi
ảnh và download không còn khớp; đã thêm CI web riêng. Test mới chưa được chạy.
Các finding bên dưới mô tả thời điểm review, không phải tất cả vẫn chưa xử lý.

## Kết luận

Đủ nền tảng cho MVP demo local có người kiểm tra/sửa kết quả. Chưa đủ bằng chứng
để công bố sản phẩm trích xuất tự động chính xác hoặc dịch vụ public ổn định.
Đây là review code và artifact sẵn có; không chạy test, OCR, model hay benchmark mới.
Không thay code runtime hoặc image trong lượt review này.

## Bằng chứng vận hành đã đọc

SQLite của container submission-web-1 có 7 job: 5 job trả kết quả (4 partial,
1 succeeded), 2 failed vì Address already in use. Bốn bản ghi cuối đều trả kết
quả: 39.44, 40.88, 36.42, 41.71 giây. Không dùng tỷ lệ 5/7 làm reliability của
bản mới: hai lỗi thuộc giai đoạn trước bản vá, số mẫu ít và không phải bộ thử có
kiểm soát. Không dùng succeeded làm nhãn đúng: nó chỉ phản ánh trạng thái/issues.
Các partial cuối có cảnh báo bố cục địa chỉ; không đủ căn cứ kết luận địa chỉ sai.
Không có bản review confirmed trong 7 job này, nên artifact chưa chứng minh luồng
lưu/xác nhận/tải bản sửa đã được người dùng hoàn tất.

Build image, web startup, GPU/model checksum preflight đã có bằng chứng trước đó.
Người dùng đã thực sự chạy inference trong Docker qua các job trên; tuy nhiên
chưa audit output so với ảnh/GT trong lượt này. Chưa kiểm định tar trên máy khác.

## Findings ưu tiên

### 1. P1 trước sản phẩm: thiếu đánh giá độ chính xác trên bộ chốt

Refined bảo toàn exact OCR spans, nhưng semantic guard tiền là advisory và tên/
địa chỉ trùng span chỉ bị cảnh báo. Cơ chế không bảo đảm chọn đúng thực thể hoặc
tổng tiền. `status=ok` không chứng minh chính xác, selection_confidence chưa có.
Các lỗi MINIMART ghép địa chỉ vào tên đã biết vẫn không được giải quyết bằng
boundary vì tính năng đó đã gỡ. OCR mất ký tự cũng không được model tự phục hồi.

Hành động: chốt tập 30–50 biên lai không dùng để chỉnh prompt, đa dạng bố cục/
độ nghiêng/ngôn ngữ; đánh giá từng field, độ đủ địa chỉ, lẫn tên/địa chỉ, tiền,
null, review và lỗi vận hành. Báo riêng OCR/selection/assembly. Chốt ngưỡng chấp
nhận với nhóm trước đánh giá; giữ yêu cầu người dùng review cho MVP.

### 2. P2 lỗi code: phản hồi Lưu có thể ghi đè thao tác mới trong form

`static/app.js` save() gửi snapshot values, chỉ đối chiếu generation (thay ảnh),
rồi fill(latest) khi response về. Input listener chỉ đặt dirty=true và không có
edit revision hoặc khóa form lúc lưu. Khi gõ tiếp sau lúc gửi, response cũ vẫn
fill lại snapshot đã lưu và xóa dirty, làm mất phần vừa gõ trên UI. Revision DB
ngăn xung đột giữa request nhưng không giải quyết cuộc đua này trong form.

Hành động: theo dõi edit revision khi gửi, giữ thay đổi mới khi response về;
hoặc khóa thao tác form trong lúc lưu và hiển thị trạng thái. Chặn double-submit.
Viết test browser giả lập phản hồi chậm và edit/save/confirm liên tiếp.
Đây là phân tích đường code, chưa tái hiện bằng browser trong lượt review.

### 3. P2 khoảng trống CI: API web tests có thể bị skip

CI `.github/workflows/tests.yml` chỉ uv sync --extra dev; dev extra chỉ có pytest.
`tests/test_web_api.py` dùng importorskip fastapi/httpx, trong khi web deps nằm
trong requirements/web.lock và không được workflow này cài. Vì vậy CI xanh
không bảo đảm API web tests đã chạy. Không có bước smoke Docker trong workflow.

Hành động: thêm job CI web riêng với requirements/web.lock + pytest, yêu cầu test
web không bị skip vì thiếu dependency; kiểm tra upload/review/download/session,
cancel, TTL và lifecycle bằng fake engine. GPU inference smoke có thể giữ manual.
Không chạy lại CI/tests trong review này, không khẳng định trạng thái CI hiện tại.

### 4. P2 giới hạn hiệu năng/công suất

Ở bốn job cuối, OCR load + Qwen load khoảng 26.8–30.9 giây/lượt; tổng lượt khoảng
36–42 giây. Exclusive giải phóng và nạp lại model giữa giai đoạn/lượt theo thiết
kế. Chỉ một inference job chạy một lúc, hàng đợi mặc định 4; người sau có thể
phải chờ nhiều lượt. Đây là số từ lịch sử người dùng, không phải benchmark.

Hành động: dùng exclusive cho demo hiện tại, nêu rõ thời gian chờ. Chỉ chuyển
resident sau khi đo VRAM đỉnh qua nhiều ảnh và xác minh cancel/timeout/OOM; không
chỉ dựa trên GPU trống trước nạp. Chưa có số đo đủ để khuyến nghị bật resident.

### 5. P2 trước public: giới hạn mô hình triển khai

Compose chỉ bind localhost, định danh bằng cookie phiên; chưa có đăng nhập/tài
khoản, rate limit chống tạo nhiều phiên hoặc quản lý người dùng. Giới hạn session/
queue/upload đang có phù hợp demo local nhưng không thay cơ chế dịch vụ public.
Cookie Secure mặc định false phù hợp HTTP localhost; public cần TLS và cấu hình
cookie/proxy tương ứng. Không mở 0.0.0.0 trên host rồi coi đó là triển khai public.

Healthcheck Docker dùng /health/live; coordinator có thể unavailable nhưng web
vẫn sống và healthcheck vẫn xanh. /health/ready báo đúng trạng thái coordinator
nhưng không bảo đảm model đã nạp, không liên tục kiểm tra GPU/worker. Chưa có
phục hồi coordinator tự động khi preflight/cleanup thất bại; thường cần restart.
Container hiện không cấu hình restart policy. Cần giám sát readiness, lỗi và
quy trình phục hồi trước khi vận hành không có người trực.

## Giới hạn còn lại, không coi là lỗi mới đã tái hiện

- Prompt gọn có thể vẫn vượt context 8192 trên biên lai dài; hiện báo lỗi thay
  vì truncate. Cần kiểm định compact prompt không làm giảm accuracy.
- Cache ready không thay kiểm tra sức khỏe mọi dependency sau khởi động.
- Dữ liệu tạm TTL theo created, xóa định kỳ khi coordinator hoạt động. Code có
  DELETE jobs/reviews; SQLite container secure_delete=1, WAL. Chưa kiểm thử đảm
  bảo xóa dữ liệu tận gốc, WAL/backup, lỗi cleanup hoặc chính sách retention public.
- SQLite và quota đĩa là biện pháp mức ứng dụng; DELETE không tự thu nhỏ file DB.
  Chưa kiểm thử vận hành dài ngày, quota khi nhiều request upload cùng lúc,
  restart, hết đĩa, mất kết nối, hai tab hoặc OOM.
- Docker bundle khoảng 9.5 GB, NVIDIA GPU và architecture 89. Chưa cam kết chạy
  trên mọi GPU/máy chấm. Cần thử docker load + compose + receipt trên máy thứ hai.
- source.zip hiện là snapshot runtime/build, không phải toàn bộ repo/test/docs.
  Cần bàn giao repo/commit tương ứng nếu muốn tái lập review và CI đầy đủ.
- Chưa review lỗ hổng dependency theo advisory hiện hành. Không suy từ version
  pin hoặc build thành công thành kết luận dependency an toàn.

## Trước khi chốt nộp MVP

1. Sửa cuộc đua form lưu và bảo đảm test web thực sự được chạy trong CI.
2. Người dùng test cùng bản image: 10–20 ảnh liên tiếp, hủy giữa OCR/Qwen,
   lỗi ảnh, hai tab, sửa/lưu/xác nhận/download hai phiên bản, restart và giữ dữ liệu.
3. Kiểm tra bốn field trên ảnh, ghi từng sai sót; đừng chỉ xem request không lỗi.
4. Test gói tar trên máy thứ hai, ghi driver/GPU và image checksum đúng.
5. Đóng băng phiên bản source/image đã test. Không đổi default sang resident
   trước khi đo và kiểm chứng.

Không cần thêm model/feature mới để hoàn thành các bước này. Tách mốc MVP có
review bằng tay khỏi mốc sản phẩm tự động/public để tránh công bố quá mức.
