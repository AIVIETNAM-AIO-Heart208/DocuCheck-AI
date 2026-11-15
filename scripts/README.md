# Các điểm vào CLI

Chạy từ thư mục gốc repository. Xem docs/WEB_DEMO.md và docs/QWEN_DEMO.md trước
khi chạy OCR/model. Các script sau không tự chạy khi khởi động web:

| Mục đích | Script |
| --- | --- |
| Web demo | `serve_web.py` |
| Chuẩn bị bundle offline | `prepare_web_models.py` |
| Một ảnh → bốn field JSON | `extract_receipt.py` |
| Demo OCR → Qwen, quản lý server | `demo_ocr_qwen.py` |
| Trích xuất từ OCR JSONL | `extract_receipt_fields.py` |
| OCR / runtime CUDA | `run_ocr.py`, `run_ocr_cuda.py` |
| Tải weights/runtime | `download_ocr_model.py`, `download_recognition_models.py`, `download_qwen_model.py` |
| Chọn ảnh/đánh giá extraction | `prepare_qwen_test_batch.py`, `evaluate_qwen_demo.py` |
| Benchmark web khi được chủ động gọi | `benchmark_web.py` |

`audit_*`, `review_*` là công cụ chẩn đoán. Các script `*psm*`,
`*recognition_benchmark*`, `compare_ocr_engines.py`, `evaluate_ocr.py`,
`analyze_psm_comparison.py` phục vụ nghiên cứu, giữ cùng test và báo cáo.
`prepare_dataset.py`/`audit_dataset.py` chuẩn bị và audit dataset local.

Không xóa script nghiên cứu khi chưa kiểm tra notebook/test/provenance tham
chiếu. Cấu hình Tesseract là baseline lịch sử, không phải OCR web hiện tại.
