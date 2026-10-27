# DocuCheck AI — Ý tưởng sản phẩm

> Tài liệu thảo luận của team Conquer. Chưa quyết định kiến trúc kỹ thuật hay mô hình.
> Cập nhật: 27/10/2026.

## 1. Tóm tắt ý tưởng trong một phút

**DocuCheck AI** là công cụ giúp người dùng **biến ảnh hóa đơn/biên lai thành dữ liệu có cấu trúc, phát hiện những điểm cần kiểm tra và xác nhận lại thông tin ngay trên tài liệu gốc**.

Thay vì phải mở từng ảnh hóa đơn và gõ thủ công các thông tin, người dùng chỉ cần cung cấp ảnh. Hệ thống đề xuất tên cửa hàng, ngày giao dịch, tổng tiền và những trường có thể đọc được. Nếu phát hiện thông tin bị thiếu, khó đọc hoặc phép tính không nhất quán (khi có đủ dữ kiện), hệ thống đưa ra cảnh báo kèm vị trí tương ứng trên ảnh để người dùng kiểm tra.

**Giá trị chính không nằm ở việc “đọc chữ từ ảnh” đơn thuần**, mà là tạo ra **dữ liệu có thể kiểm chứng**: mỗi thông tin quan trọng cần có nguồn trên hóa đơn, trạng thái rõ ràng và khả năng được người dùng sửa/xác nhận.

### Một câu giới thiệu project

> **DocuCheck AI — Trợ lý số hóa và kiểm tra biên lai/hóa đơn tiếng Việt có dẫn chứng từ tài liệu gốc.**

### Nhóm người dùng mục tiêu ban đầu

- Sinh viên hoặc cá nhân muốn lưu và tra cứu các khoản chi tiêu qua ảnh biên lai.
- Câu lạc bộ, ban tổ chức sự kiện, nhóm quản lý quỹ cần tổng hợp chứng từ chi phí.
- Cửa hàng/nhóm kinh doanh nhỏ cần giảm nhập liệu thủ công.

**Nhóm sử dụng ưu tiên để demo:** người phụ trách tổng hợp chi phí của một câu lạc bộ hoặc một sự kiện, vì bài toán dễ hiểu và không yêu cầu kết nối hệ thống kế toán thực tế.

---

---

## 2. Vấn đề thực tế DocuCheck AI muốn giải quyết

### 2.1. Những khó khăn hiện có

1. **Hóa đơn có rất nhiều kiểu bố cục:** tên nơi bán, ngày, tổng tiền có thể nằm ở vị trí khác nhau.
2. **Ảnh chụp không đồng nhất:** lệch góc, bóng đổ, mờ, giấy in nhiệt phai khiến nhận dạng không chắc chắn.
3. **Đọc được chữ chưa đồng nghĩa hiểu đúng:** một hóa đơn có nhiều số tiền như tạm tính, giảm giá, thuế, tiền khách đưa, tiền thối lại và số tiền thực thanh toán.
4. **Người dùng khó biết hệ thống lấy giá trị từ đâu:** một con số sai nhưng được xuất thẳng ra bảng sẽ rất khó rà soát.
5. **Dữ liệu có thể không nhất quán:** ví dụ tổng thanh toán khác phép tính từ các thành phần — nhưng chỉ có thể kết luận “cần kiểm tra”, không mặc định là gian lận.

### 2.2. Câu hỏi cốt lõi của sản phẩm

**“Làm sao biến một hóa đơn dạng ảnh thành bản ghi chi tiêu có thể tin cậy và kiểm chứng được, với ít thao tác thủ công hơn?”**

Điều này quan trọng hơn câu hỏi “Làm thế nào để AI nhận dạng tất cả chữ trên hóa đơn?”.

### 2.3. Các tác vụ người dùng thực sự muốn hoàn thành

| Việc cần làm | Người dùng mong nhận được |
|---|---|
| Lưu lại một hóa đơn | Một bản ghi chứa ngày, nơi bán, số tiền, ảnh gốc |
| Không muốn nhập thủ công | Hệ thống tự đề xuất các giá trị đọc được |
| Nghi ngờ có dữ liệu bị đọc nhầm | Bấm vào giá trị và xem đúng chỗ xuất hiện trên ảnh |
| Cần rà lại số tiền | Cảnh báo khi dữ liệu đủ để đối chiếu nhưng kết quả không khớp |
| Muốn dùng dữ liệu cho báo cáo | Bản ghi đã được người dùng xác nhận và có cấu trúc thống nhất |

---

---

## 3. Ví dụ trực quan: một phiên sử dụng DocuCheck AI

Giả sử người dùng tải lên ảnh một biên lai có nội dung:

| Nội dung in trên biên lai (minh họa) | Giá trị |
|---|---:|
| Cửa hàng | MINI MART ABC |
| Ngày | 20/10/2026 |
| Tạm tính | 150.000 đ |
| Giảm giá | 10.000 đ |
| Thuế/phí bổ sung | 0 đ |
| **Tổng thanh toán in trên giấy** | **160.000 đ** |

DocuCheck AI dự kiến xử lý theo trải nghiệm người dùng như sau:

**Bước 1 — Đọc và tạo bản ghi:** hiện tên nơi bán, ngày giao dịch và các số tiền hệ thống tìm được.  
**Bước 2 — Đối chiếu:** nếu đã nhận diện **đầy đủ** các thành phần và quy tắc tính phù hợp, hệ thống tính `150.000 - 10.000 + 0 = 140.000 đ`.  
**Bước 3 — Thông báo có điều kiện:** hiển thị “Tổng in trên biên lai là 160.000 đ; tổng tính từ các trường được nhận diện là 140.000 đ. Hãy kiểm tra khoản phí khác hoặc giá trị đã đọc.”  
**Bước 4 — Kiểm chứng:** người dùng nhấn vào `total` để thấy vùng chứa “160.000 đ” trên ảnh, rồi sửa hoặc xác nhận.  
**Bước 5 — Lưu:** chỉ bản ghi đã rà soát mới được xem là **đã xác nhận**.

> Đây là ví dụ **giả lập** để làm rõ ý tưởng, không phải kết quả một mô hình đã chạy. Nếu hóa đơn thiếu trường, tổng tiền có cấu trúc khác, hoặc hệ thống không đọc chắc các khoản, DocuCheck AI phải báo **không đủ dữ kiện để đối chiếu**, thay vì kết luận hóa đơn sai.

### Giá trị khác biệt team nên hướng tới

1. **Có bằng chứng (evidence-grounded):** biết một giá trị đến từ dòng/vùng nào trên tài liệu.
2. **Biết khi nào không chắc:** phân biệt `không có trên hóa đơn`, `có nhưng không đọc được` và `đọc được nhưng cần xác minh`.
3. **Kiểm tra có điều kiện:** không tính toán/kết luận khi thiếu cấu phần.
4. **Người dùng giữ quyền quyết định:** AI đề xuất, người dùng xác nhận phiên bản cuối.

Những tính năng riêng lẻ này không hoàn toàn mới trên thị trường; **điểm mạnh phải nằm ở độ hoàn thiện và chất lượng trải nghiệm tổng hợp**, đặc biệt với hóa đơn tiếng Việt.

---

---

## 4. Nên giới hạn phạm vi ý tưởng như thế nào?

### 4.1. Phạm vi đề xuất cho phiên bản đầu

**Chỉ làm:** hóa đơn bán lẻ và biên lai thanh toán **một trang**, ưu tiên ảnh chụp có tiếng Việt, bố cục tương đối rõ.

**Không gộp ngay vào cùng bài toán:** hợp đồng dài, căn cước, chứng từ y tế nhạy cảm, hóa đơn điện tử nhiều trang phức tạp, kiểm toán thuế hay phát hiện hóa đơn giả.

Lý do là cách định nghĩa “thông tin đúng”, các trường cần đọc và cơ sở dữ liệu gán nhãn khác nhau đáng kể. Chọn một miền hẹp giúp team có thể nói chính xác **sản phẩm làm được gì và chưa làm được gì**.

### 4.2. Chia trường dữ liệu thành hai nhóm

**Nhóm A — Trường lõi, có sẵn nguồn nhãn tương đối phù hợp**

| Trường đề xuất | Ý nghĩa | Có trong MC-OCR? |
|---|---|---|
| `seller_name` | Tên cửa hàng | Có: `SELLER` |
| `seller_address` | Địa chỉ nơi bán | Có: `SELLER_ADDRESS` |
| `transaction_datetime` | Ngày/giờ giao dịch | Có: `TIMESTAMP` |
| `total_amount` | Tổng tiền | Có: `TOTAL_COST` |

**Nhóm B — Trường mở rộng, cần xem kỹ nhãn và/hoặc bổ sung dữ liệu của team**

| Trường đề xuất | Dùng để làm gì? | Rủi ro dữ liệu |
|---|---|---|
| `receipt_id` | Định danh chứng từ | Không phải trường KIE chuẩn trong MC-OCR |
| `subtotal` | Tính/đối chiếu trước giảm giá | Không có nhãn trực tiếp trong MC-OCR |
| `discount` | Khoản giảm giá | Xuất hiện không đồng đều trên các hóa đơn |
| `tax` / `service_fee` | Thành phần cộng thêm | Không phải hóa đơn nào cũng trình bày riêng |
| `line_items` | Tên món hàng, số lượng, đơn giá | Dữ liệu phức tạp hơn đáng kể, dễ sai liên kết dòng |

**Quy tắc quan trọng:** Không nên tuyên bố sản phẩm kiểm tra được “tổng tiền có chính xác không” cho **mọi** hóa đơn ngay từ đầu. Kiểm tra số học chỉ khả thi trên **những mẫu mà team có đủ trường được gán nhãn và xác minh**.

### 4.3. Ranh giới trách nhiệm của hệ thống

DocuCheck AI có thể đưa ra **cảnh báo dữ liệu**, không được tự nhận là hệ thống **xác thực pháp lý hoặc phát hiện gian lận**. Một số sai lệch có thể do phí ẩn, thuế đã bao gồm trong đơn giá, cách làm tròn, chiết khấu theo dòng hoặc lỗi nhận dạng.

---

---

## 8. Những quyết định team cần thống nhất trước khi lập kế hoạch

Đây là các **câu hỏi về sản phẩm và dữ liệu**, chưa phải phân công hay triển khai:

1. **Chân dung người dùng đầu tiên là ai?** Ví dụ: ban tài chính câu lạc bộ cần tổng hợp chứng từ, thay vì “mọi người sử dụng tài liệu”.
2. **Phạm vi chứng từ chính xác là gì?** Ảnh biên lai mua hàng một trang tại Việt Nam; có bao gồm phiếu thu, hóa đơn VAT, hóa đơn điện tử hay không?
3. **Chọn lời hứa sản phẩm ở mức nào?** Chỉ trích xuất 4 trường có bằng chứng, hay thêm kiểm tra số học trên một nhóm hóa đơn có đủ nhãn?
4. **Nhóm có thể truy cập MC-OCR hợp lệ không?** Nếu chưa chắc, cần chủ động xây dữ liệu nội bộ tối thiểu để không phụ thuộc nguồn bị hạn chế.
5. **Team có thể tạo bao nhiêu hóa đơn mẫu và gán nhãn đáng tin cậy?** Điều này sẽ quyết định độ rộng của trải nghiệm kiểm tra.
6. **Có chấp nhận giới hạn rõ trường hợp “không đủ dữ kiện” không?** Nên **có** — đây là đặc trưng của sản phẩm đáng tin cậy, không phải điểm yếu cần che giấu.

### Đề xuất phạm vi để team dễ đồng thuận

> **DocuCheck AI phiên bản đầu:** Ứng dụng hỗ trợ số hóa **ảnh biên lai bán lẻ tiếng Việt**, trích xuất **tên cửa hàng, địa chỉ, ngày/giờ, tổng tiền**, hiển thị vùng bằng chứng, thông báo dữ liệu thiếu hoặc không chắc chắn và cho phép xác nhận. Với những biên lai **có đủ thông tin tạm tính, giảm giá, thuế/phí được gán nhãn**, ứng dụng bổ sung kiểm tra tính nhất quán của tổng thanh toán.

Cách định vị này vừa **thành thật với dữ liệu công khai hiện có**, vừa tạo không gian cho phần “Check” khác biệt so với OCR thuần túy.

---

---

## Kết luận

DocuCheck AI hướng đến **trích xuất dữ liệu có bằng chứng + cảnh báo có điều kiện + người dùng xác nhận** cho biên lai bán lẻ tiếng Việt. Đây là **ý tưởng và phạm vi đề xuất**, chưa phải cam kết tính năng đã triển khai.

Chi tiết nguồn dữ liệu: [docs/datasets.md](datasets.md).
