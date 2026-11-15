# Chế độ trích xuất và bằng chứng

## Baseline và refined

CLI hỗ trợ `baseline` và `refined`, mặc định `baseline`. Web mặc định
`refined`; chính sách GPU mặc định `exclusive`. Cả hai nhận output của
PHOCR–VietOCR hiện tại. Tên mode không xác định phiên bản OCR cũ hay mới.

Refined đưa văn bản OCR, định danh, bbox và cấu trúc dòng/khối vào Qwen:

- Tên và địa chỉ: model chọn mảng ID vùng hoặc phần chữ được cung cấp.
- Tiền và ngày giờ: model chọn ID ứng viên có nguồn hoặc null.
- Code kiểm tra nguồn/span, sắp xếp theo hình học và chuẩn hóa kết quả.
- Semantic guard đưa cảnh báo, không tự bảo đảm chọn đúng vai trò.

Nhóm ghép và khoảng cách là gợi ý bố cục, không phải nhãn thực thể chắc chắn.
Cùng một khối có thể chứa cả tên và địa chỉ. OCR mất chữ hoặc parser bỏ sót
đáp án hợp lệ vẫn có thể khiến kết quả sai/thiếu.

## Demo một ảnh

Setup môi trường GPU và trọng số theo [hướng dẫn web](WEB_DEMO.md), rồi chạy:

```powershell
.\.venv\Scripts\python.exe scripts/extract_receipt.py "receipt.jpg" --extraction-mode refined --output outputs/receipt.json
```

CLI thông báo đường dẫn log/diagnostics; stdout chứa JSON bốn trường. Bỏ
`--extraction-mode refined` để dùng baseline. Xem [CLI chi tiết](QWEN_DEMO.md)
cho batch và OCR cache; chỉ tái sử dụng cache có profile tương thích.

## Đọc kết quả

JSON công khai chỉ gồm `seller_name`, `seller_address`,
`transaction_datetime`, `total_amount`. Null là chưa trích xuất được,
không chứng minh trường không tồn tại trên ảnh.

Trong thư mục run, OCR nằm ở `ocr/predictions.jsonl`; `inputs/`, `layout/`,
`text_spans/`, `candidates/`, `requests/`, `responses/`, `decisions/` và
`extractions.jsonl` phục vụ truy nguyên. Không cần gửi diagnostics thô cùng
kết quả cho người dùng.

`needs_review` yêu cầu đối chiếu thêm; `ok` không phải nhãn đúng. Confidence
OCR không phải xác suất chọn đúng trường. Tên/địa chỉ có thể lẫn hoặc thiếu
thành phần; địa chỉ nhiều dòng và ảnh nghiêng cần được kiểm tra trên ảnh.
Context hiện tại 8192 token, dự trữ đầu ra 512 token; quá budget có thể báo lỗi.

So sánh lựa chọn cần cùng OCR và nhãn tham chiếu đã chốt. Ví dụ đúng ở
pipeline trước không tự xác nhận accuracy refined hiện tại. Tham khảo
[báo cáo kỹ thuật](../reports/DocuCheck_AI_Technical_Report.pdf) để biết
bằng chứng và phạm vi kết quả.
