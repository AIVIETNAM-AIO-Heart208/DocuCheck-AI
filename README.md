# DocuCheck AI

DocuCheck AI nghiên cứu cách trích xuất và rà soát thông tin trên ảnh hóa đơn, biên lai bán lẻ tiếng Việt. Hệ thống hướng tới tạo bản ghi có cấu trúc, chỉ rõ vùng ảnh làm bằng chứng cho từng giá trị và để người dùng kiểm tra, xác nhận kết quả.

## Trạng thái

Đã có luồng CLI OCR PHOCR/VietOCR CUDA → Qwen3-4B Q4_K_M → bốn field JSON,
cùng source web demo upload, review/xác nhận và đóng gói Docker Linux GPU.
Web/Docker mới được triển khai, **chưa chạy kiểm thử, inference hoặc build Docker
để xác minh**. Không dùng số benchmark Tesseract lịch sử dưới đây làm chất lượng
của hệ thống Qwen hiện tại.

- [Web demo: setup Windows/Docker, hướng dẫn sử dụng và giới hạn](docs/WEB_DEMO.md).
- [Đóng gói nộp online/offline và điều kiện máy chấm](docs/DOCKER_SUBMISSION.md).
- [CLI một ảnh → JSON và OCR mới nhất](docs/QWEN_DEMO.md).

Web mặc định refined + GPU exclusive để bảo thủ VRAM; resident là tùy chọn cần
kiểm chứng. CLI giữ mặc định baseline. Đọc tài liệu web trước khi cài môi trường
GPU; lệnh core/Tesseract phía dưới phục vụ workflow nghiên cứu riêng.

Ngày 05/11/2026 đã chạy **Week 2 — Goal 1: benchmark recognition trên 6.585 crop**.
Validation đạt CER **20,65%**, WER **56,18%**, exact-match **23,69%** với cấu hình
Tesseract PSM 7 cố định. Xem [báo cáo và giới hạn](docs/WEEK2_REPORT.md),
[protocol](docs/WEEK2_RECOGNITION_PROTOCOL.md) và [cách chạy lại](docs/PIPELINE.md).

So sánh full-page PSM 6/4/11 đã chạy đủ 231 ảnh và đánh giá lại sau khi sửa
parser transcript nguồn. PSM 11 có CER 0,6084 / WER 0,8160 trên phần GT có chữ;
lợi thế so với PSM 6 còn nhỏ. Goal 2 đã hoàn tất đối chiếu 20 ca, giữ rõ các
giới hạn và nhận xét chưa thống nhất, chưa đổi cấu hình production. Xem
[báo cáo PSM và các giới hạn](docs/PSM_COMPARISON_REPORT.md).

## Phạm vi ban đầu

Nghiên cứu tập trung vào biên lai bán lẻ một trang, ưu tiên tiếng Việt. Các trường dự kiến gồm tên nơi bán, địa chỉ, ngày/giờ giao dịch và tổng tiền. Chỉ kiểm tra số học khi có đủ thành phần và quy tắc phù hợp; sai lệch là lý do để rà soát, không phải bằng chứng gian lận.

Xem [product brief](docs/idea.md) để biết giả định về người dùng và nguyên tắc sản phẩm. Kết quả thực tế của Week 1 nằm trong [báo cáo](docs/WEEK1_REPORT.md), [schema dữ liệu](docs/DATA_SCHEMA.md) và [bàn giao Week 2](docs/WEEK2_HANDOFF.md).

## Cấu trúc repository

```text
docs/       Tài liệu dự án
data/       Dataset cục bộ (không commit)
notebooks/  Phân tích dữ liệu tương tác
src/        Mã nguồn dùng lại
scripts/    Quy trình chạy qua dòng lệnh
tests/      Kiểm thử tự động
outputs/    Kết quả sinh cục bộ (không commit)
```

## Môi trường phát triển

Yêu cầu Python 3.12 và Tesseract 5. Cài Tesseract bằng trình quản lý gói của hệ điều hành (ví dụ `sudo apt install tesseract-ocr`). Tạo môi trường Python và cài các dependency đã khóa trong `uv.lock`:

```bash
uv sync --all-extras
source .venv/bin/activate
uv run pytest
jupyter lab
```

Dataset mặc định nằm ở `data/mcocr`; khi đặt ở vị trí khác, truyền `--dataset-root` cho CLI hoặc đặt biến `MC_OCR_ROOT`.

Để tải MC-OCR từ Kaggle, cài Kaggle CLI và cấu hình thông tin xác thực Kaggle (`~/.kaggle/kaggle.json` hoặc `KAGGLE_API_TOKEN`), sau đó chạy từ thư mục gốc repository:

```bash
uv tool install kaggle
kaggle datasets download \
  -d domixi1989/vietnamese-receipts-mc-ocr-2021 \
  -p data/mcocr --unzip
```

Dataset được giải nén vào `data/mcocr`, thư mục local bị Git ignore. Kiểm tra điều khoản dataset trên Kaggle trước khi sử dụng hoặc phân phối lại.

## Luồng dữ liệu và OCR

Sau khi tải dataset và cài môi trường, làm theo [hướng dẫn pipeline](docs/PIPELINE.md) để tạo manifest, audit dữ liệu (tùy chọn), chạy OCR và đánh giá. Hướng dẫn này liệt kê đầu vào, đầu ra và thứ tự của từng bước.

Định nghĩa manifest nằm trong [schema dữ liệu](docs/DATA_SCHEMA.md); chi tiết audit annotation ở [protocol review](docs/ANNOTATION_AUDIT.md); quy tắc baseline và chỉ số OCR ở [Goal 3](docs/GOAL3_OCR_BASELINE.md).

## Dữ liệu và quyền riêng tư

Không commit ảnh biên lai thật, nội dung biên lai, thông tin cá nhân, dữ liệu bị giới hạn phân phối, model checkpoint hoặc bí mật truy cập. Kiểm tra điều khoản dataset trước khi sử dụng hoặc phân phối lại. Mọi cảnh báo trong tương lai chỉ hỗ trợ rà soát, không thay thế xác minh pháp lý hay kết luận gian lận.
