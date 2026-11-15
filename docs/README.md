# Tài liệu dự án

## Chạy và bàn giao ứng dụng

- [Docker Hub](DOCKER_HUB.md): người nhận pull và chạy image.
- [Setup web](WEB_DEMO.md): môi trường local, GPU, review và cấu hình.
- [Đóng gói Docker](DOCKER_SUBMISSION.md): build/push và bàn giao offline.
- [CLI OCR → Qwen](QWEN_DEMO.md): xử lý ảnh, batch và tái sử dụng OCR.
- [Chế độ trích xuất](QWEN_GUARD_LAYOUT_REFINEMENT.md): baseline/refined và bằng chứng.
- [Báo cáo kỹ thuật](../reports/DocuCheck_AI_Technical_Report.pdf).
- [Hướng dẫn phát triển](../CONTRIBUTING.md).

## Dữ liệu và tái lập nghiên cứu

- [Schema dữ liệu](DATA_SCHEMA.md): manifest, nhãn, split và trạng thái dữ liệu.
- [Pipeline nghiên cứu](PIPELINE.md): chuẩn bị dữ liệu, OCR và đánh giá.
- [Audit annotation](ANNOTATION_AUDIT.md): quy trình kiểm tra nhãn.
- [Protocol recognition](OCR_RECOGNITION_PROTOCOL.md): cách đo trên crop.
- [Protocol PSM ban đầu](PSM_COMPARISON_PROTOCOL.md) và [bản hiệu chỉnh](PSM_CORRECTED_PROTOCOL.md): phân đoạn trang và sửa cách đọc transcript.

Các protocol được giữ để script tái lập cấu hình và nguồn. Tesseract trong
thí nghiệm nghiên cứu không phải OCR mặc định của web. Không lưu prompt giao
việc, bàn giao tạm hoặc báo cáo tuần trong thư mục này.
