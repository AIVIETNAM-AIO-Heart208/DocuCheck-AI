# Product brief

## Mục đích

DocuCheck AI nghiên cứu cách chuyển ảnh biên lai tiếng Việt thành bản ghi có cấu trúc để người dùng đối chiếu với chứng từ gốc. Hệ thống cần chỉ ra nguồn của từng giá trị, thể hiện rõ mức độ chưa chắc chắn và để người dùng xác nhận kết quả cuối.

## Phạm vi ban đầu

- Biên lai bán lẻ một trang, ưu tiên tiếng Việt.
- Đề xuất tên nơi bán, địa chỉ, ngày/giờ giao dịch và tổng tiền khi chứng từ có thông tin tương ứng.
- Liên kết mỗi đề xuất với vùng bằng chứng trên ảnh, cho phép người dùng rà soát hoặc sửa.
- Nêu thông tin thiếu, khó đọc hoặc có thể không nhất quán mà không xem sự chưa chắc chắn là bằng chứng gian lận.

Danh sách mặt hàng, chứng từ nhiều trang, kiểm toán thuế, xác minh pháp lý và phát hiện gian lận nằm ngoài phạm vi ban đầu.

## Nguyên tắc sản phẩm

1. **Ưu tiên bằng chứng:** chỉ rõ vùng nguồn cho mỗi giá trị được trích xuất.
2. **Thể hiện sự chưa chắc chắn trung thực:** chỉ phân biệt thông tin không có, không đọc được hay không được gán nhãn khi dữ liệu cho phép xác định.
3. **Chỉ kiểm tra khi đủ căn cứ:** đối chiếu số học cần có các thành phần liên quan và quy tắc phù hợp; nếu thiếu, báo chưa đủ dữ kiện.
4. **Người dùng quyết định:** kết quả AI là đề xuất cho đến khi người dùng rà soát.

## Trường dự kiến và giả định về dataset

| Trường sản phẩm | Nhãn MC-OCR dự kiến |
|---|---|
| `seller_name` | `SELLER` |
| `seller_address` | `SELLER_ADDRESS` |
| `transaction_datetime` | `TIMESTAMP` |
| `total_amount` | `TOTAL_COST` |

Các ánh xạ nhãn này lấy từ ghi chú dự án và cần được xác minh với dataset đã tải trước khi sử dụng. Nhãn KIE không đồng nghĩa dataset có bản chép đầy đủ nội dung biên lai để đánh giá OCR. Chưa giả định dataset có nhãn cho tiền trước thuế, giảm giá, thuế, phí dịch vụ, mã biên lai hay danh sách mặt hàng.

## Nhóm người dùng cần tìm hiểu trước

Demo ban đầu có thể tập trung vào người tổng hợp chi phí cho câu lạc bộ sinh viên hoặc sự kiện. Đây là quy trình cụ thể và không cần kết nối hệ thống kế toán. Theo dõi chi tiêu cá nhân và cửa hàng nhỏ có thể là nhóm người dùng về sau.

## Các quyết định còn mở

- Xác nhận nhóm người dùng đầu tiên và loại biên lai trong phạm vi.
- Kiểm tra điều khoản truy cập dataset, độ bao phủ nhãn thực tế và nhu cầu tự gán nhãn bổ sung.
- Xác định phép kiểm tra nào có đủ dữ liệu hỗ trợ và cách thông báo trường hợp thiếu căn cứ.

Tài liệu này mô tả định hướng đề xuất, không khẳng định tính năng đã triển khai hay chất lượng mô hình đã được đo lường.
