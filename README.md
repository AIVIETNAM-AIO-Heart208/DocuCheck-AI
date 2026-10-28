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

Tải model tiếng Việt đã pin revision/checksum vào thư mục local bị ignore:

```bash
uv run python scripts/download_ocr_model.py
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

Tạo manifest chuẩn hóa cục bộ và các split phát triển tái lập bằng:

```bash
uv run python scripts/prepare_dataset.py \
  --dataset-root data/mcocr \
  --output-dir data/processed \
  --seed 42 \
  --validation-fraction 0.2
```

Manifest chứa `internal_train`/`internal_dev` do team tạo theo SHA-256 ảnh và seed cố định, cùng `official_validation_inventory` để giữ nguyên nguồn chính thức. Ảnh train trùng chính xác với validation chính thức được cách ly khỏi hai split nội bộ. Ảnh validation hiện không có nhãn KIE trong export cục bộ; OCR ground truth đầy đủ chỉ có ở một phần ảnh train. Manifest và nội dung nhận dạng nằm trong `data/processed/` và không được commit.

`recognition_manifest.jsonl` là các cặp crop/transcript từ task text-recognition riêng, không phải KIE field crops và chưa có liên kết parent receipt được xác minh. Schema 1.1 giữ raw annotations, provenance và các trạng thái thiếu/lỗi riêng biệt; xem [DATA_SCHEMA](docs/DATA_SCHEMA.md).

Chạy audit gần trùng và tạo mẫu review annotation 40 ảnh (seed cố định):

```bash
uv run python scripts/audit_dataset.py --dataset-root data/mcocr --seed 42 --sample-size 40 --threshold 6 --output-dir outputs/audit/week1
```

Mở `outputs/audit/week1/annotations.html` và `near_duplicates.html` trên máy local. Làm theo [protocol review](docs/ANNOTATION_AUDIT.md), ghi kết quả vào worksheet; candidate gần trùng chưa phải duplicate được xác nhận. CLI không thay split và không ghi đè worksheet có sẵn. Chọn thư mục output mới khi chạy lại. Trên PowerShell có thể thay `uv run python` bằng `.venv\Scripts\python.exe` sau khi cài môi trường.

Chạy OCR mẫu trên ba ảnh phát triển trước, rồi mới chạy toàn bộ split nội bộ:

```bash
uv run python scripts/run_ocr.py --split internal_dev --limit 3 --output-dir outputs/ocr/smoke
uv run python scripts/run_ocr.py --split internal_dev --output-dir outputs/ocr/tesseract_internal_dev
uv run python scripts/evaluate_ocr.py --split internal_dev --output-dir outputs/ocr/evaluation
```

Baseline dùng Tesseract LSTM tiếng Việt (`vie`) với word boxes TSV. Predictions, metrics theo từng ảnh/vùng và transcript chỉ được ghi vào `outputs/ocr/`; không chạy benchmark trên official validation/test khi thiếu ground truth phù hợp. Mở bốn notebook trong `notebooks/` để audit, EDA, xác nhận xử lý và phân tích lỗi bằng ảnh local.

## Dữ liệu và quyền riêng tư

Không commit ảnh biên lai thật, nội dung biên lai, thông tin cá nhân, dữ liệu bị giới hạn phân phối, model checkpoint hoặc bí mật truy cập. Kiểm tra điều khoản dataset trước khi sử dụng hoặc phân phối lại. Mọi cảnh báo trong tương lai chỉ hỗ trợ rà soát, không thay thế xác minh pháp lý hay kết luận gian lận.
