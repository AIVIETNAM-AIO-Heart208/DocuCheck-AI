# Rà soát nội dung và trình bày Week 2

Ngày lập: 06/11/2026, Asia/Saigon.

## Bản hiện hành: bổ sung nguồn tham khảo chính thức

Bản hiện hành có **11 trang A4**, dành trang cuối cho tài liệu tham khảo. Đã mở và đối chiếu năm nguồn gốc: ban tổ chức MC-OCR, tài liệu Tesseract, kho VietOCR của pbcquoc, tài liệu PaddleOCR và JiWER. Link trực tiếp kèm ngày truy cập 06/11/2026; xác minh PDF có đủ năm URI. Trích dẫn gắn với dữ liệu nền, định nghĩa PSM/CER/WER hoặc cấu hình model, không dùng nguồn bên ngoài để chứng thực số liệu thí nghiệm của nhóm.

Đã biên dịch ba lượt, render và xem toàn bộ 11 trang; không có lỗi bố cục/tham chiếu. Các đoạn mô tả bản 10 trang dưới đây là lịch sử biên tập. QA và delivery manifest hiện tại áp dụng cho PDF 11 trang mới.

## Rà soát văn phong bản nộp

Đã rà soát lại theo yêu cầu về tính chuyên nghiệp, tên file và ngôn ngữ hội thoại. Bản trước còn tên model dạng file `vie.traineddata` và các cụm “workspace hiện tại”, “lượt biên tập”, “người dùng xác nhận”, “không phải ảnh OCR mô phỏng”. Đã đổi thành mô tả model tiếng Việt, giới hạn hồ sơ thực nghiệm và trạng thái thẩm định; không thay đổi số liệu hoặc nâng mức chắc chắn của kết luận.

Đã rút nội dung kể quá trình viết báo cáo, Việt hóa một số tiêu đề/caption, gọn lại tài liệu tham khảo và giữ nguyên bất định Goal 3. Tên tài liệu tham khảo được diễn đạt bằng tiếng Việt; đường dẫn tới các tài liệu gốc nằm trong EVIDENCE_INDEX.md.

Bản PDF mới vẫn 10 trang, đã render và xem từng trang. Kiểm tra text không tìm thấy tên file/đường dẫn nội bộ hoặc các cụm hội thoại đã liệt kê. Metadata ghi tác giả là nhóm, công cụ tạo là LaTeX/MiKTeX. Đây là rà soát chất lượng biên tập, không phải phép phát hiện hoặc chứng nhận tác giả có/không sử dụng AI. Tên DocuCheck AI và AI-VIETNAM là tên dự án/đơn vị đào tạo, được giữ nguyên.

EVIDENCE_INDEX.md và các file kỹ thuật vẫn chứa đường dẫn để kiểm chứng. Phạm vi không có tên file áp dụng cho PDF dành cho người đọc, không áp dụng cho mã nguồn và hồ sơ truy xuất.

Kế thừa bìa, font và màu navy/teal của Week 1; cập nhật tuần/ngày và dòng chủ đề. Không ghi Module 05 hay số submission vì nguồn hiện có chỉ xác nhận thông tin của Week 1. Tên nhóm và thành viên giữ nguyên.

Bố cục có tóm tắt, phạm vi, phương pháp chung, ba goal, thảo luận và kế hoạch tiếp theo. PDF không có đường dẫn artifact, lệnh chạy, checksum hoặc log. Tài liệu tham khảo xác định các hồ sơ nội bộ và nguồn nhóm cung cấp; đường dẫn chi tiết ở EVIDENCE_INDEX.md.

Các điểm biên tập chính:

- CER/WER full-page sai GT chỉ được giải thích như đính chính, không lặp bảng lịch sử không hợp lệ.
- Mẫu số Goal 2 được nêu trước bảng; phép gán text/hình học có bảng riêng và giới hạn rõ ràng.
- PSM 11 được đề xuất có điều kiện, kèm kết quả bootstrap đã lưu và các trường hợp kém hơn PSM 6.
- Biểu đồ ca 01/05/07 giúp thấy chiều tác động khác nhau giữa ảnh, không dùng để ước lượng tỷ lệ lỗi.
- Goal 3 ghi rõ nguồn nhóm cung cấp; khác biệt runtime xuất hiện cả trong PDF và hồ sơ minh chứng.
- Không đổi từ “đã phân tích” thành “đã phân xử nhãn”; phản hồi bất định và bất đồng được giữ.
- Hai biểu đồ là vector từ số đo đã có. Không tái phân phối ảnh hoặc text của hóa đơn.
- Những kiểm tra tự động ngày 06/11 chỉ đọc/hash/cộng số đã lưu; không chạy OCR, metric evaluator hoặc test suite.

Kết quả QA cuối: **10 trang A4**, gồm bìa và 9 trang nội dung. Đã biên dịch ba lượt và xem toàn bộ 10 PNG ở 110 dpi. Bản đầu có một đoạn runtime tràn sang trang riêng; đã biên tập gọn để bỏ trang thưa. Bản cuối không còn lỗi tràn lề, chồng chữ, glyph tiếng Việt, tiêu đề lẻ hoặc tham chiếu chưa giải quyết. Bảng và biểu đồ có thể đọc ở kích thước trang bình thường.

Đã kiểm tra tọa độ chữ, nội dung số liệu trọng yếu và header/footer. Hash của PDF và từng trang render nằm trong `evidence/pdf_qa.json`. Có 638 tệp được bảo vệ khớp hash trước/sau. Bộ Goal 1 khớp 75 mục inventory; bộ Goal 2 corrected khớp 216 mục; review cuối khớp 11 mục. Tất cả là kiểm tra đọc tệp, không chạy lại OCR, evaluator hoặc suite.


## Điều chỉnh phạm vi tài liệu tham khảo theo yêu cầu

Chỉ giữ năm nguồn công khai có link; bỏ năm mục nội bộ không có link và các trích dẫn số tương ứng. Nguồn số liệu nhóm vẫn ghi ở caption và truy nguyên trong hồ sơ minh chứng. Tên nhóm trên bìa và metadata được khôi phục; không còn tên nhóm ở mục tài liệu tham khảo. PDF vẫn 11 trang. Đã xem các trang thay đổi; các trang còn lại có hash render giống bản đã kiểm tra.
