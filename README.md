# DocuCheck AI

DocuCheck AI nghiên cứu cách trích xuất và rà soát thông tin trên ảnh hóa đơn, biên lai bán lẻ tiếng Việt. Hệ thống hướng tới tạo bản ghi có cấu trúc, chỉ rõ vùng ảnh làm bằng chứng cho từng giá trị và để người dùng kiểm tra, xác nhận kết quả.

## Trạng thái

Dự án đang ở giai đoạn chuẩn bị dữ liệu và nghiên cứu. Định hướng sản phẩm mới là đề xuất; OCR, trích xuất thông tin, kiểm tra và ứng dụng cho người dùng chưa được xem là tính năng đã triển khai.

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

Dataset mặc định nằm ở `data/mcocr`; khi đặt ở vị trí khác, truyền `--dataset-root` cho CLI hoặc đặt biến `MC_OCR_ROOT`. Giá trị trong `configs/week1.yaml` chỉ là đường dẫn tương đối trong workspace.

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
