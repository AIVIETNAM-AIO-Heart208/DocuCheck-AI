# Rà soát và chỉnh sửa báo cáo

**Lưu ý phiên bản (29/10/2026):** Tài liệu này ghi lần rà soát bản kỹ thuật 19 trang. Bản hiện tại trong main.pdf đã được viết lại thành báo cáo 5 trang dành cho người xem; các nhận xét về bố cục và nội dung PDF cũ chỉ có giá trị lịch sử.

Ngày rà soát: 28/10/2026. Phạm vi: bìa, nội dung kỹ thuật, khả năng đọc biểu đồ và tính nhất quán của hồ sơ báo cáo. Không sửa mã dự án, dataset hoặc kết quả thực nghiệm.

## Kết luận đối chiếu ba goal với repo

**Báo cáo phản ánh đúng phạm vi ba goal và các kết quả có trong repo.** Không phát hiện sai số tổng hợp hoặc claim hoàn thành chức năng ngoài Week 1 trong lượt đối chiếu này. Khác biệt quan trọng nằm giữa tài liệu lịch sử và artifact hiện có, đặc biệt ở Goal 3; không nên ép PDF lặp lại số cũ chỉ để giống tài liệu.

| Goal | Đối chiếu với repo | Kết luận và giới hạn cần giữ |
|---|---|---|
| Goal 1 — Dataset Understanding & EDA | `loader.py`, `eda.py`, `duplicates.py`; schema, báo cáo Week 1; manifest, review CSV và near-duplicate artifacts | Đúng inventory 1.546 receipt, 6.585 vùng KIE và 6.585 crop riêng; review 6/32/2; 20 receipt cách ly và 36 ứng viên gần trùng. Không biến mẫu tìm lỗi thành tỷ lệ lỗi toàn tập, không xem crop là KIE field crops. |
| Goal 2 — Reproducible Data Processing | `preprocessing.py`, `splitting.py`, `validation.py`, `prepare_dataset.py`; các test policy/rollback; bundle A/B, skip và failure report | Đúng schema 1.1, seed 42, split 904/231/20/391, policy và verifier. Tái kiểm validation 8.131 bản ghi. Bundle mặc định thiếu checksum metadata khác với bundle hardening đã verify; đây là điểm phải phân biệt khi nghiệm thu. |
| Goal 3 — OCR Baseline & Error Analysis | `baseline.py`, `inference.py`, `metrics.py`, notebook 04, model config/runtime và prediction/evaluation | Đúng baseline Tesseract-only trên 231 ảnh dev, PSM 6/OEM 1. Current artifact: 26.859 boxes, CER 1,8725, WER 2,1448; tái tính khớp toàn bộ summary và per-image/per-region. Phân tích lỗi ở mức chẩn đoán; chưa có taxonomy nguyên nhân do người review gán nhãn, KIE accuracy hoặc detection F1. |

**Kiểm chứng mới:** hash 79 source/artifact không đổi; `skip` có 1.431 receipt và mọi receipt giữ nguyên nội dung/split so với manifest mặc định; failure report xác nhận policy `fail` và 115 lỗi. Không chạy preparation hoặc lặp thí nghiệm fail/rollback trên dữ liệu thật. Chi tiết tại `evidence/goal_alignment_review.json`.

## Những phần thừa đã cắt hoặc gộp trong lượt này

- Bỏ biểu đồ số vùng KIE vì lặp nguyên số liệu bảng nhãn; giữ bảng để còn đồng thời đối chiếu số vùng, số ảnh có nhãn và số ảnh chưa gán.
- Bỏ hộp “Cơ sở đánh giá” lặp quy ước minh chứng ở đầu báo cáo; rút thông tin workspace, các câu nhắc không chạy lại và những cảnh báo phạm vi đã được giải thích ở đúng mục chuyên môn.
- Rút chi tiết biên tập như lỗi checksum đánh máy trong tài liệu cũ khỏi thân bài; chi tiết đối soát vẫn nằm trong evidence index.
- Rút đoạn diễn giải runtime và lịch sử tests; giữ nguồn, môi trường và sự phân biệt historical/local/CI.
- Bỏ các ngắt trang cố định giữa tiểu mục để nội dung liền mạch; giữ bảng/hình gần phần giải thích. Bản tinh gọn là 19 trang, trong đó 13 trang nội dung chính.

**Bổ sung cần thiết:** kết quả thực tế của `skip`/`fail` trong hồ sơ hardening và tiểu mục đánh giá Goal 2 rõ ràng. Các số này được gắn là artifact có sẵn, không trình bày như preparation mới.

Không cắt các giới hạn về mẫu audit, structural validity, leakage gần trùng, alignment OCR và KIE chưa triển khai: đây là điều kiện để đọc đúng kết quả, không phải phần thừa.

## Các điểm đã sửa

| Vị trí | Vấn đề bản trước | Điều chỉnh |
|---|---|---|
| Bìa | Các khối căn trái rời rạc; phiên bản có khung và nhiều đường phân cách vẫn gây cảm giác chia vụn | Thiết kế lại tối giản theo trục giữa, bỏ khung bao; AI-VIETNAM và AIO2026 tạo khối đầu trang, tiêu đề tuần nằm trên tên dự án |
| Bìa | Metadata quá nhỏ, nhiều dòng “chưa cung cấp”, hộp nền và commit kỹ thuật làm bìa nặng | Dùng bảng thông tin tác giả không nền, cỡ chữ lớn hơn; commit vẫn có ở phần mốc kiểm tra và phụ lục |
| Bìa / checklist | “Ngày lập / ngày nộp dự kiến” dễ gợi một lịch nộp chưa được cung cấp | Chỉ ghi ngày lập báo cáo; không tự xác định hạn nộp |
| Biểu đồ EDA và lỗi OCR | Font gốc 10 pt tiếp tục bị thu nhỏ khi chèn vào A4 | Tăng font lên 12 pt, điều chỉnh kích thước canvas, ngắt nhãn dài; giữ nguyên dữ liệu và số bins |
| Bảng phân tích lỗi OCR | Dòng “Nhận dạng OCR” dùng lỗi transcript quan sát trong dự án làm bằng chứng, dễ trộn lỗi annotation với lỗi engine | Chỉ mô tả prediction và sai khác sau ghép; ghi rõ chưa tách nguyên nhân OCR/GT/alignment bằng review từng ca |

## Trạng thái sẵn sàng nộp và giới hạn đã công bố

1. **Thông tin bìa đã hoàn tất theo yêu cầu.** Đơn vị **AI-VIETNAM**, khóa học **AIO2026**, nhóm **Winner Winner Chicken Dinner**; thành viên **Nguyễn Văn Minh** và **Nguyễn Thành Trung**. Người dùng yêu cầu bỏ mã học viên và giảng viên; không còn placeholder cho các trường này.
2. **Nguồn OCR chưa đồng nhất.** Artifact hiện có ghi Tesseract 5.5.3.20260724, còn YAML/tài liệu lịch sử ghi 5.3.4. PDF đã tách hai bối cảnh đúng cách; vẫn thiếu snapshot riêng của lần chạy cũ để đối chiếu độc lập. Không thể giải quyết thiếu chứng cứ bằng biên tập câu chữ.
3. **Bundle mặc định có metadata cũ.** Manifest gốc đạt cấu trúc nhưng thiếu checksum metadata cho verifier mới. Hai bundle hardening A/B có bằng chứng tốt hơn; khi nộp cần xác định rõ bộ nào đi kèm PDF, không trộn chúng.
4. **CI chưa có bằng chứng thành công.** File workflow và tests local không thay thế log/check-run CI. Báo cáo giữ trạng thái chưa xác minh.
5. **Minh chứng chi tiết chưa được đóng gói cùng PDF.** Manifest, prediction, alignment và review CSV đang ở local. Danh sách phải gửi riêng nằm trong `EVIDENCE_INDEX.md`; bản PDF không thay thế các tệp này nếu yêu cầu nộp có minh chứng thực nghiệm.
6. **Phân tích lỗi còn ở mức chẩn đoán.** Chưa có taxonomy nguyên nhân được con người gán từng ca OCR; 36 ứng viên gần trùng chưa phân xử. Audit KIE không tự chứng minh lỗi transcript toàn trang. Các giới hạn đã nêu trong PDF và không ngăn hoàn thành mục tiêu baseline tuần đầu.

## Kiểm tra nghiệm thu cuối

**PDF đã hoàn thiện trong phạm vi báo cáo Week 1.** Lượt kiểm tra cuối không phát hiện lỗi nội dung mới cần sửa source LaTeX. Đã kiểm tra 79 hash nguồn/artifact và 21 tệp của manifest báo cáo đầu vào; source/PDF khớp hash QA, không còn placeholder, 17 label không trùng/thiếu đích tham chiếu, 5 bibliography keys hợp lệ, hai figure PDF tồn tại và được sử dụng. Validation cấu trúc đạt 8.131 bản ghi; số prediction/word boxes và phép tính CER/WER khớp artifact cùng hồ sơ tái tính trước đó. Chi tiết: `evidence/final_review.json`.

Các việc còn lại khi nộp bộ hồ sơ là cung cấp snapshot notebook đúng hash và artifact chi tiết qua kênh được phép nếu yêu cầu có minh chứng. Không cần huấn luyện KIE, phân xử toàn bộ gần trùng hoặc chạy lại thí nghiệm lịch sử chỉ để hoàn thiện phần viết của báo cáo tuần đầu. Kết quả tests 106 passed vẫn thuộc lần chạy gốc đã lưu; lượt nghiệm thu cuối không chạy lại suite hoặc inference.

## Nhận xét biên tập

Phần nội dung có cơ sở chứng cứ và phân biệt khá rõ kết quả hiện tại với lịch sử. Điểm yếu còn lại là mật độ đường dẫn/mã E cao, khiến giọng văn đôi lúc thiên về hồ sơ kiểm chứng. Các đường dẫn cần cho yêu cầu truy vết đã được giữ; nên đọc bản nộp cùng phụ lục thay vì đưa thêm log hoặc transcript vào thân bài. Không rút các cảnh báo quan trọng chỉ để báo cáo trông tích cực hơn.

Việc rà soát này không thực thi lại OCR inference, preparation, notebook hoặc suite tests. Kết quả 106 tests là lần chạy đã lưu trong hồ sơ trước đó; lượt này kiểm tra hash nguồn/artifact, tái tính evaluation từ prediction, đối chiếu dữ liệu `skip`/failure report, biên dịch PDF mới và xem trang render. Kết quả build và QA được ghi trong `evidence/pdf_qa.json`.
