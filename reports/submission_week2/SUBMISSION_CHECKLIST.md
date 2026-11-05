# Kiểm tra báo cáo Week 2

Ngày: 06/11/2026. PDF cuối: **11 trang A4** (bìa, 9 trang nội dung và tài liệu tham khảo). Trạng thái kiểm tra ghi trong `evidence/pdf_qa.json`.

- [x] Dùng tên nhóm/thành viên và phong cách Week 1; không suy số submission hoặc module cho Week 2.
- [x] Có đầy đủ ba goal, phương pháp, kết quả, phân tích và giới hạn.
- [x] Goal 1 tách train/validation, coverage/prediction rỗng/lỗi thực thi và exact-match.
- [x] Goal 2 dùng corrected GT, đủ mẫu số, phân biệt text scope/geometry scope.
- [x] Không dùng CER/WER full-page sai GT từ Week 1 để xếp hạng hoặc tính cải thiện.
- [x] Review giữ trạng thái xác nhận/bất định/bất đồng; không bịa người review.
- [x] Goal 3 giữ số nhóm cung cấp và ghi phần không thể xác minh.
- [x] Không trộn Tesseract 5.5.3 của Goal 1 với 5.3.4 của Goal 3.
- [x] Có bảng ba goal, crop benchmark, PSM, ba engine và biểu đồ CER/WER riêng.
- [x] Có minh họa định lượng ca lỗi thật, không sao chép raw receipt/transcript hoặc tạo ảnh OCR giả.
- [x] Số test lịch sử gắn đúng lượt chạy; không nhận đã chạy lại suite.
- [x] Kế hoạch tiếp theo có detector, đánh giá end-to-end và KIE riêng.
- [x] Rà soát văn phong bản nộp: PDF không còn tên file/đường dẫn nội bộ hoặc câu mang ngữ cảnh hội thoại/biên tập với trợ lý; giữ giới hạn bằng chứng.
- [x] Bổ sung năm nguồn chính thức có link và ngày truy cập; phân biệt thông tin phương pháp với số đo nội bộ. Kiểm tra đủ năm URI trong PDF.
- [x] Biên dịch XeLaTeX ba lượt, render và xem cả 11 trang bản cuối; không có lỗi tràn, glyph hoặc tham chiếu trong log; tọa độ chữ nằm trong trang.
- [x] Đối chiếu 638 tệp được bảo vệ không đổi sau khi tạo báo cáo, gồm Week 1, các bundle Week 2, docs/src/tests và hai manifest.

Đây là bộ báo cáo local, không xác nhận đã upload hoặc giảng viên nghiệm thu. Không commit/push.
