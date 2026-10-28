# Quy trình và kết quả audit annotation cục bộ

## Trạng thái hiện hành — 2026-10-28

Đã hoàn tất kiểm tra trực quan **40/40 ảnh gốc và overlay KIE**. Kết quả nằm trực tiếp trong **outputs/audit/week1/annotation_review.csv**, reviewer **Minh Nguyễn**: **32 incorrect, 6 correct, 2 uncertain**, không có ảnh chưa review. Sáu dòng uncertain=yes đã được xem lại bằng ảnh gốc, overlay và crop/phóng lớn/tăng tương phản phù hợp; quyết định và cờ phân loại được giữ vì chưa có bằng chứng đủ để thay đổi. Ghi chú sáu dòng đã bổ sung kết quả tái kiểm.

CSV là nguồn trạng thái review hiện hành. annotation_sample.jsonl, audit_summary.json và tiêu đề trong annotations.html giữ metadata lúc sinh mẫu; not_reviewed, human_review_status=not_performed hoặc chữ “pending” trong các artifact đó không phản ánh kết quả CSV sau review. Lệnh sinh audit tự nó không thực hiện đánh giá trực quan.

| Cờ trong CSV | Số ảnh yes | Số ảnh uncertain |
|---|---:|---:|
| wrong_label | 8 | 2 |
| wrong_geometry | 6 | 0 |
| missing_field_annotation | 21 | 5 |
| unreadable_text | 3 | 0 |
| uncertain | 6 | 0 |

Các nhóm chồng lấp. Sáu ảnh có phần chưa rõ khác với hai ảnh có kết luận tổng thể uncertain. Có ít nhất **19 ảnh có bằng chứng transcript nguồn khác ảnh** được ghi rõ trong notes; **năm ảnh chỉ sai transcript**, nên incorrect dù các cờ nhãn/hình học/thiếu đều no. Danh sách và phân tích đầy đủ nằm trong [WEEK1_REPORT.md](WEEK1_REPORT.md), không suy tỷ lệ này cho toàn dataset.

## Tái lập bộ review mà không ghi đè kết quả

Sau khi có manifest, lệnh đã dùng để sinh bộ audit là:

~~~bash
uv run python scripts/audit_dataset.py --dataset-root data/mcocr --seed 42 --sample-size 40 --threshold 6 --output-dir outputs/audit/week1
~~~

**Thư mục week1 hiện chứa CSV đã review.** CLI sẽ từ chối ghi đè worksheet; nếu cần sinh bộ khác, phải chọn thư mục output mới. --mode annotations hoặc --mode near-duplicates chỉ chạy phần tương ứng. Mọi output chứa ảnh/đường dẫn/nội dung hóa đơn phải giữ cục bộ. Không tạo CSV review hoàn tất thứ hai trong lần hoàn tất Goal 1 này.

Lần xác minh cuối dùng trực tiếp các API trong bộ nhớ: select_annotation_audit_sample() tái tạo đúng mẫu, audit_near_duplicates() tái tạo đúng ứng viên; không chạy lại chế độ sinh worksheet vào thư mục hiện hữu.

## Chọn mẫu và bằng chứng hình ảnh

select_annotation_audit_sample() trong eda.py chọn 40 ID khác nhau từ nguồn train với seed 42. Hàm sắp tầng theo số phần tử tăng dần, trộn ứng viên xác định trong từng tầng rồi lấy luân phiên không hoàn lại. Các tầng chồng lấp gồm cảnh báo geometry KIE/OCR, nhãn chưa ánh xạ, KIE rỗng, OCR GT thiếu/không đầy đủ, tứ phân vị thấp/cao của Laplacian, tổ hợp trường và số vùng KIE (ngưỡng bốn vùng). Ảnh train bị cách ly do trùng chính xác vẫn có thể được chọn; không chọn inventory validation chính thức.

Mẫu này được tăng cường ca bất thường để tìm lỗi. **32/40 = 80% không phải tỷ lệ annotation sai toàn bộ dataset.** Muốn ước lượng tỷ lệ quần thể cần thiết kế lấy mẫu đại diện hoặc kiểm tra rộng hơn. Laplacian là heuristic độ chi tiết, không phải nhãn chất lượng thật. Notebook 01/02 đã có phân tích độ phân giải, tỷ lệ ảnh, trường, vị trí/kích thước vùng, mật độ và heuristic chất lượng; không cần thêm biểu đồ trùng nội dung.

annotations.html hiển thị polygon nguồn, chỉ số vùng từ 0, raw label và canonical field; annotation_sample.jsonl giữ lý do chọn và metadata. Ảnh overlay ở outputs/audit/week1/overlays/; đường dẫn ảnh gốc tra qua image_path trong data/processed/manifest.jsonl, tương đối với data/mcocr.

Cảnh báo geometry tổng hợp có thể đến từ **OCR sidecar**, không phải KIE. Khi cần, xem riêng ocr_regions bằng plot_standardized_record(..., region_key="ocr_regions"). Không suy cảnh báo số học thành lỗi nhìn thấy trên polygon KIE.

## Quy tắc điền và kiểm tra worksheet

1. Chỉ đặt review_status=reviewed sau khi xem pixel ảnh gốc và annotation. annotation_correctness nhận correct, incorrect hoặc uncertain.
2. Các cờ wrong_label, wrong_geometry, missing_field_annotation, unreadable_text, uncertain nhận yes, no, uncertain; giữ bất định nếu thiếu bằng chứng.
3. region_indices là chỉ số vùng hiện hữu từ 0, ngăn bằng dấu chấm phẩy. Trường bị thiếu hoàn toàn không có chỉ số vùng để tự tạo. field dùng canonical field, nhiều trường ngăn bằng dấu chấm phẩy.
4. evidence_notes ghi tiếng Việt, nêu vùng đúng/sai, bằng chứng đọc được, phần thiếu/không rõ và so sánh nguồn. Không chép toàn bộ hóa đơn hoặc thông tin cá nhân không cần thiết.
5. Giữ reviewer Minh Nguyễn, ngày YYYY-MM-DD. Chỉ đổi ngày khi thực sự xem lại ảnh. Không thêm cột phân biệt loại reviewer hoặc thay raw annotation.
6. correct không đi kèm lỗi xác nhận chưa được giải thích; incorrect phải có lý do cụ thể. Sai transcript riêng không tự biến thành sai nhãn hoặc polygon. uncertain=yes phải nêu phần còn chưa biết.

Các nhóm lỗi dùng để phân tích:

- **A — Sai nhãn:** semantic label không phù hợp nội dung, ví dụ ngày mang ADDRESS hoặc tổng mang TIMESTAMP.
- **B — Sai geometry:** vùng lệch, nằm ngoài nội dung hoặc chỉ bao một mảnh nghiêm trọng; khoảng đệm nhỏ hoặc ảnh xoay không tự là lỗi.
- **C — Thiếu annotation:** trường mục tiêu hiện rõ, có liên quan nhưng chưa được thể hiện đầy đủ.
- **D — Sai transcript:** text nguồn khác chữ trên ảnh; ghi trong notes do schema CSV hiện tại không có cột riêng.
- **E — Không đọc được:** nhòe, phai, che khuất khiến một phần đánh giá không đáng tin cậy.
- **F — Loại chứng từ/phạm vi:** báo cáo Z, phiếu bếp hoặc quy tắc ngữ nghĩa chưa được xác định. Mẫu có ba báo cáo Z và hai phiếu bếp cần chính sách riêng; phiếu bếp vẫn có thể có annotation hiện hữu đúng.
- **G — Tiền xử lý/hiển thị:** chỉ xác nhận khi nguồn đúng nhưng bản chuẩn hóa hoặc hiển thị sai. Chưa phát hiện lỗi loại này trong mẫu; toàn bộ 6.585 vùng KIE khớp nhãn/text/tọa độ nguồn.

Năm ca chỉ sai transcript đã được kiểm tra lại: 7c7e572191a3635426719c5f, 722e66275e9d41f1bd5eb81d, c2c26d54d0d0e87addb147a4, e11ba834772075019f08aacd, 84f6e585510121d045f6e0f3. Giữ nguyên cờ nhãn/geometry/thiếu bằng no là phù hợp bằng chứng, không phải mâu thuẫn CSV.

## Các ca chưa thể kết luận hết

| Image ID | Kết luận sau tái kiểm |
|---|---|
| 37c7371fec6064b857b4fc49 | Overall uncertain: nhòe nặng, mảng nguồn rỗng; crop/tăng tương phản không phục hồi được chữ để xác nhận trường bị thiếu. |
| f19ab1e6366ca6617a368607 | Overall uncertain: báo cáo Z có nhiều tổng khác nhau, thiếu quy tắc ánh xạ ngày/tổng sang hóa đơn giao dịch. |
| b76c50e8d9a4ea33d09e22a2 | Incorrect do thiếu tên/địa chỉ nhìn thấy; phần gấp che khiến tổng tiền chưa thể kiểm tra. |
| 4042bd22a6543500ded1084a | Incorrect do tiêu đề phiếu bếp gán SELLER; ngày phai và khả năng thiếu trường còn bất định. |
| fc4def26d678d4ecf728ac12 | Incorrect do ngày kinh doanh gán SELLER và lỗi transcript; giữ bất định về KIE cho báo cáo Z. |
| a45d3b8c307e428fa84a1b54 | Incorrect do transcript tiền sai; ngày hệ thống/tổng báo cáo Z còn bất định về ý nghĩa trường. |

[Tài liệu tác vụ MC-OCR](https://www.rivf2021-mc-ocr.vietnlp.com/) cho phép một số trường không xuất hiện hoặc không đọc được; [định dạng chính thức](https://www.rivf2021-mc-ocr.vietnlp.com/dataset) mô tả annotation nhưng không giải thích riêng báo cáo Z/phiếu bếp. Vì thế không yêu cầu mọi chứng từ có đủ bốn trường và không tự đưa ra quy tắc phân xử thay tài liệu nguồn.

Chủ dự án cần phân xử phần tranh chấp/bất định trước khi dùng làm GT đánh giá cuối. Việc còn bất định đã được ghi nhận không ngăn hoàn tất Goal 1 về hiểu/khảo sát dữ liệu. Kết quả hiện tại không được mô tả là đã sửa sạch nguồn hoặc đã có xác nhận độc lập thứ hai.

## Diễn giải trường thiếu và phân biệt nguồn lỗi

summarize_field_missingness() chia bản ghi thành with_label, without_label_annotation và ground_truth_unavailable. Hai số with_invalid_geometry, with_missing_or_empty_text có thể chồng lên bản ghi đã gán nhãn. Nhãn lạ được đếm riêng. confirmed_field_absent=null nghĩa là chưa có bằng chứng vắng mặt, không có nghĩa số trường thực sự vắng mặt bằng 0.

Các phát hiện A–D ở đây dựa trên **annotation nguồn KIE so với pixel**, không phải lỗi suy diễn từ OCR predictions. ocr_regions là GT transcript toàn trang khác KIE; các polygon vượt biên trong đó không phải box Tesseract. Thống kê OCR baseline/CER/WER ở Goal 3 có giao thức riêng và không được chạy lại trong task này.

Khi sửa dữ liệu ở bước sau: giữ raw bất biến, ghi phiên bản phân xử/sửa riêng có lý do và liên kết ID/vùng; sửa nhãn, text, geometry hoặc bổ sung vùng theo đúng loại lỗi đã xác nhận. Với ca E/F, quy định cách xử lý/loại khỏi từng phép đánh giá trước khi chấm model. Không tự suy trường thiếu từ số nhãn ít hơn bốn, không bỏ vùng lỗi âm thầm và không dùng mẫu này để công bố chất lượng toàn tập.

## Audit nghi gần trùng

near_duplicates.html và near_duplicate_candidates.jsonl hiện chứa **36 cặp ứng viên chưa phân xử**. Đã tái tính pHash và đối chiếu toàn bộ kết quả: 10 cặp train/dev, 22 train/validation chính thức, bốn dev/validation chính thức; 1.526 ảnh băm được, không lỗi đọc. Chưa kết luận các cặp là cùng giao dịch.

Khi phân xử ở bước sau, so thông tin riêng của giao dịch thay vì chỉ bố cục cửa hàng, ghi quyết định cùng giao dịch / khác giao dịch / chưa rõ và viện dẫn cả hai ID. Chỉ tạo artifact phân xử khi bước đó được thực hiện; lần hoàn tất này không sinh thêm review CSV. Không tự gộp, xóa hoặc chuyển split.

near_duplicate_summary.json giữ phương pháp, ngưỡng 6, số so sánh và số ứng viên; lỗi đọc nằm trong near_duplicate_failures.jsonl. pHash hiện dùng grayscale 32×32, DCT 8×8 và 63 bit AC. Nó có thể báo nhầm bố cục giống và không bảo đảm chống xoay/cắt/phối cảnh. Không có ứng viên cũng không chứng minh hết leakage; danh sách hiện tại cần phân xử trước khi chốt benchmark.

## Kiểm chứng cuối

Đã xác minh UTF-8/pandas, 40 dòng/13 cột, ID/thứ tự khớp sample, enum hợp lệ, reviewer/ngày/chỉ số vùng và ghi chú riêng từng ảnh. Source KIE/manifest, hình học, checksum ảnh, tái lập mẫu và ứng viên pHash đều đã kiểm tra. Bộ unit tests hiện có **60 passed, 0 failed**; notebook 01/02 đều thực thi thành công, mỗi notebook bảy code cells. Xem báo cáo Week 1 cho toàn bộ số liệu, rủi ro và nghiệm thu Goal 1.
