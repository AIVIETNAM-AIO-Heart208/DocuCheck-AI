# DocuCheck AI

Web demo trích xuất bốn trường từ ảnh biên lai: `seller_name`, `seller_address`,
`transaction_datetime`, `total_amount`. Người dùng tải ảnh, kiểm tra bằng chứng,
sửa/xác nhận và tải JSON. Kết quả AI cần được đối chiếu với biên lai.

Pipeline hiện tại: **PHOCR detector → VietOCR CUDA → Qwen3-4B-Instruct-2507
Q4_K_M → JSON → review**. OCR dùng E1 scale 2 Lanczos và padding có guard.
Tesseract là baseline nghiên cứu lịch sử, không phải engine của web demo.

[Đọc báo cáo kỹ thuật](reports/DocuCheck_AI_Technical_Report.pdf)
về phương pháp, kết quả và giới hạn của hệ thống.

## Docker Hub: pull và chạy, không cần model riêng

Sau khi publisher build target `bundled` và push theo
[hướng dẫn Docker Hub](docs/DOCKER_SUBMISSION.md), người nhận chạy:

```powershell
docker pull heart2082006/docucheck-ai
docker run -d --name docucheck-ai --init --gpus all --cpus 4 --memory 10g -p 127.0.0.1:8000:8000 -v docucheck-data:/var/lib/docucheck -e EXTRACTION_MODE=refined -e GPU_POLICY=exclusive heart2082006/docucheck-ai
```

Mở http://localhost:8000. Cần NVIDIA GPU và Docker hỗ trợ GPU. Không cần gửi
ZIP/model/Compose riêng. Target bundled mới được chuẩn bị, chưa build/push hoặc
kiểm chứng inference trong lượt thay đổi này.

## Chạy bản Docker offline được bàn giao trước đó

Yêu cầu NVIDIA GPU và Docker hỗ trợ GPU; Windows dùng Docker Desktop với Linux
containers/WSL2. Bản build hiện tại nhắm RTX 4060 (architecture 89).

Giải nén gói bàn giao, mở terminal trong `submission`:

```powershell
docker load --input .\docucheck-ai.tar
docker compose up -d --no-build --pull never
```

Mở **http://localhost:8000**. Xem log bằng `docker compose logs -f web`; dừng
bằng `docker compose down`. Giữ `models/` cạnh `compose.yaml`.

Web mặc định `refined` + GPU `exclusive`. Resident là tùy chọn chưa được xác
nhận đủ VRAM. Sửa source không tự cập nhật container, tar hoặc ZIP. Xem
`BUILD_STATUS.md` trong gói để biết phiên bản và những bước đã kiểm chứng.

## Phát triển và demo local

- [Setup web, bundle model, cấu hình và cách dùng](docs/WEB_DEMO.md).
- [Build/export Docker và gửi người khác](docs/DOCKER_SUBMISSION.md).
- [CLI một ảnh → JSON, batch và OCR cache](docs/QWEN_DEMO.md).
- [Mục lục hướng dẫn và protocol nghiên cứu](docs/README.md).
- [Mục lục scripts theo chức năng](scripts/README.md).
- [Hướng dẫn phát triển, kiểm tra và bàn giao](CONTRIBUTING.md).

Python yêu cầu phiên bản 3.12. Web, OCR GPU và nghiên cứu core có dependency
khác nhau, đặc biệt NumPy/Torch. Cài môi trường theo tài liệu tương ứng; không
chạy `uv sync --all-extras` trong môi trường web đang hoạt động.

CLI khi môi trường GPU đã setup:

```powershell
.\.venv\Scripts\python.exe scripts/extract_receipt.py "receipt.jpg" --extraction-mode refined --output outputs/receipt.json
```

CLI giữ default `baseline`; truyền `--extraction-mode refined` khi muốn so với
web. JSON public chỉ có bốn trường, audit và bằng chứng được lưu riêng.

## Cấu trúc repository

```text
src/docucheck/
  web/           API, UI, hàng đợi và quản lý worker/GPU
  extraction/    OCR adapter, Qwen, parser, evidence và JSON
  ocr/           Detector/recognizer và pipeline OCR
  data/          Dataset, annotation, preprocessing và split
  evaluation/    Chỉ số và so sánh OCR
  visualization/ Công cụ hiển thị bằng chứng
scripts/         CLI; xem scripts/README.md
configs/         Cấu hình model và baseline nghiên cứu
requirements/    Môi trường web và inference Docker
tests/          Unit/API và fake DOM tests
docs/           Setup, thiết kế, protocol và báo cáo
notebooks/      Nghiên cứu dữ liệu tương tác
reports/        Bằng chứng nghiên cứu đã lưu
```

Dataset `data/`, weights `models/`, kết quả `outputs/`, virtualenv, cache và
`submission/` là tài nguyên local. ZIP/TAR không đưa lên Git; gửi gói Docker qua
Drive/USB. Không commit `.env` hoặc nội dung biên lai thật.

## Kiểm chứng và giới hạn

Đã có build/startup Docker và lịch sử người dùng chạy OCR → Qwen trả kết quả.
Điều đó chưa chứng minh độ chính xác trên mọi biên lai. Tên và địa chỉ có thể bị
ghép/chọn thiếu; OCR có thể mất chữ; hóa đơn dài có thể vượt context.
`needs_review` là yêu cầu kiểm tra bằng chứng, không phải xác suất sai.

CI tách unit tests và web contracts. Fake tests không thay kiểm tra browser,
GPU hoặc ảnh thật. Refactor hiện tại chưa được chạy test hoặc đóng lại Docker.
[Báo cáo kỹ thuật](reports/DocuCheck_AI_Technical_Report.pdf) trình bày giới hạn
của MVP. Không dùng chỉ số Tesseract lịch sử làm accuracy hiện tại.
