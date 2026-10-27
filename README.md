# DocuCheck AI

**DocuCheck AI — Hệ thống số hóa và kiểm tra hóa đơn/biên lai tiếng Việt có dẫn chứng từ tài liệu gốc.**

> **Trạng thái:** Khởi tạo dự án cho AIO Conquer. Đây là giai đoạn làm rõ ý tưởng và dữ liệu, chưa có mô hình hoặc ứng dụng triển khai.

## Ý tưởng

Ứng dụng dự kiến cho phép người dùng tải ảnh biên lai một trang, tự đề xuất các trường như tên nơi bán, địa chỉ, ngày/giờ và tổng tiền, đồng thời hiển thị vùng ảnh nguồn để người dùng đối chiếu và xác nhận. Với biên lai có đủ cấu phần được nhận diện, hệ thống hướng tới cảnh báo trường thiếu hoặc số tiền không nhất quán.

**Giá trị cốt lõi:** Trích xuất có bằng chứng · Kiểm tra có điều kiện · Người dùng xác nhận.

## Tài liệu

- [Ý tưởng sản phẩm, người dùng và phạm vi đề xuất](docs/idea.md)
- [Phân tích dataset: MC-OCR, CORD-v2, SROIE và nguồn tiếng Việt](docs/datasets.md)

## Cấu trúc

```text
DocuCheck-AI/
├── README.md
├── .gitignore
├── docs/
│   ├── idea.md
│   └── datasets.md
├── src/
│   └── .gitkeep
├── data/
│   └── .gitkeep
├── notebooks/
│   └── .gitkeep
└── tests/
    └── .gitkeep
```

Các thư mục `src/`, `data/`, `notebooks/`, `tests/` đang để trống có chủ đích và sẽ được dùng khi team bắt đầu triển khai.

## An toàn và quyền sử dụng dữ liệu

Không commit ảnh hóa đơn thật, thông tin cá nhân, tài liệu nhạy cảm, API key, checkpoint lớn hoặc dữ liệu không có quyền phân phối lên repo công khai. Mọi đánh giá và cảnh báo dự kiến của AI chỉ mang tính hỗ trợ rà soát, không phải kết luận pháp lý về tính thật/giả của hóa đơn.

## Bước tiếp theo

Team đọc và thống nhất [ý tưởng](docs/idea.md) cùng [nguồn dữ liệu](docs/datasets.md) trước khi xác định scope và kế hoạch kỹ thuật.
