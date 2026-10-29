# Kiểm tra báo cáo và bộ nộp tuần 1

Cập nhật 29/10/2026 (Asia/Saigon). Bản hiện tại: 9 trang A4 gồm bìa. Chi tiết nghiệm thu tại evidence/pdf_qa.json và evidence/final_review.json.

- [x] Bìa đúng AI-VIETNAM, AIO2026, nhóm và hai thành viên; không có mã học viên/giảng viên.
- [x] Ba goal có phương pháp, kết quả, diễn giải và giới hạn; không nhận hoàn thành mô hình KIE hoặc ứng dụng.
- [x] Bảng bốn trường và EDA phân biệt số vùng/số ảnh, thiếu nhãn/trường vắng mặt.
- [x] Ba tình huống lỗi dựa trên review đã hoàn tất; không sao chép ảnh, mã ảnh hoặc transcript nhạy cảm vào PDF.
- [x] Giải thích chia theo nhóm trùng chính xác, trạng thái dữ liệu và giới hạn kiểm tra cấu trúc.
- [x] Giải thích cách ghép/tính CER/WER và giới hạn chẩn đoán; không tự gán nguyên nhân OCR.
- [x] Bảng tái lập có bốn thành phần giống hệt từng byte, đúng hai bộ đầu ra đã qua verifier; không suy rộng sang mọi môi trường hoặc độ đúng của nhãn.
- [x] Công thức CER/WER tổng hợp theo vùng, có định nghĩa ký hiệu và thay số khớp kết quả đã lưu; phân biệt rõ dấu hàng nghìn và thập phân.
- [x] PDF không có tên file, đường dẫn nội bộ, hàm/lớp, lệnh chạy, log hoặc checksum.
- [x] Biên dịch XeLaTeX và kiểm tra bản render; tham chiếu, tiếng Việt, font, bảng và hình được xác minh trong QA.
- [x] Hồ sơ CI đúng commit, run/job và log; giữ trạng thái cũ dưới nhãn lịch sử.
- [x] EVIDENCE_INDEX.md xác định bộ minh chứng tối thiểu và các phần có thể cần cung cấp có kiểm soát.
- [x] Tách hồ sơ thực nghiệm lịch sử khỏi QA hiện tại; không tuyên bố có thí nghiệm mới.
- [x] Đã chốt mã nguồn và notebook trên GitHub tại commit `461f544ddb16bf5529c17a63e9a6fbd5bda87706`; xác nhận commit tồn tại trên GitHub. Các thay đổi notebook local vẫn được giữ nguyên.
- [x] Đã chuẩn bị bộ minh chứng tổng hợp cho ba goal và ghi rõ những dữ liệu chi tiết có thể cung cấp có kiểm soát khi cần kiểm chứng sâu.
- [x] Đã kèm bốn ảnh xuất từ output notebook đã lưu, ghi rõ nguồn và cách xuất; không thực thi lại notebook hoặc lấy gallery/transcript biên lai.
- [x] Đã đối chiếu hash notebook local, output đã chọn và ảnh xuất qua hồ sơ provenance; làm rõ phạm vi đếm ảnh trùng và cách làm tròn CER/WER.
- [x] PDF trong bộ nộp giống hệt PDF của commit đã chốt và bản đã qua QA, gồm 9 trang.
- [x] Bộ nộp dùng link GitHub cho mã nguồn; ZIP final không kèm source.zip, notebook chứa output riêng tư hoặc dữ liệu biên lai gốc.
- [x] Đã kèm checklist này, hướng dẫn đọc, danh mục minh chứng và manifest; kiểm tra hash từng tệp, nội dung ZIP và CRC thành công.

**Đã hoàn tất chuẩn bị bộ nộp Week 1.** ZIP final: `outputs/submission/DocuCheck_AI_Week1_FINAL.zip`. Mã nguồn: https://github.com/AIVIETNAM-AIO-Heart208/DocuCheck-AI/tree/461f544ddb16bf5529c17a63e9a6fbd5bda87706.

Checklist xác nhận việc chuẩn bị và kiểm tra bộ nộp, không xác nhận đã upload hoặc được giảng viên nghiệm thu. Bước tiếp theo là người dùng upload ZIP final và cung cấp link GitHub. Minh chứng chi tiết chỉ được gửi bổ sung nếu có yêu cầu phù hợp.
