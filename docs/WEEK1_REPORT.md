# Báo cáo hoàn thành Week 1

## Goal 1 — Hiểu dữ liệu và phân tích khám phá (EDA)

**Kết luận cuối ngày 2026-10-28: PASS.** Đã xác minh dữ liệu cục bộ, chạy lại EDA, hoàn tất review trực quan 40/40 ảnh, tái kiểm sáu ca bất định và năm ca chỉ sai transcript, phân loại lỗi và kiểm tra tính nhất quán. Reviewer trong worksheet: **Minh Nguyễn**. PASS áp dụng cho mục tiêu hiểu, khảo sát và ghi nhận chất lượng dữ liệu; các annotation lỗi và rủi ro dưới đây vẫn cần xử lý trước khi dùng làm ground truth đáng tin cậy.

### 1. Tổng quan và nguồn dữ liệu

MC-OCR là tập ảnh hóa đơn chụp bằng thiết bị di động, có tác vụ đánh giá chất lượng ảnh và trích xuất thông tin. README của dự án hướng dẫn lấy bản export từ Kaggle; lần kiểm tra này xác minh bản đã có cục bộ, không tái tải hoặc xác nhận toàn bộ lịch sử tải. Kích thước dưới đây được tính lại từ dữ liệu thực, không lấy tổng số của cuộc thi thay cho bản export này.

| Thành phần được xác minh | Số lượng và ý nghĩa |
|---|---|
| Ảnh KIE train | 1.155 đường dẫn/ID, tương ứng 1.122 nội dung ảnh khác nhau theo SHA-256 |
| Inventory validation chính thức | 391 ảnh; CSV cục bộ không có cột nhãn/polygon KIE |
| Manifest hóa đơn | 1.546 bản ghi, 1.546 đường dẫn khác nhau, 1.491 nội dung ảnh khác nhau theo SHA-256 trên cả hai nguồn |
| Vùng KIE | 6.585 vùng của train; giữ nguyên nhãn, text và geometry nguồn |
| Transcript toàn trang | 1.151/1.155 ảnh train có sidecar, tổng 40.868 vùng; bốn ảnh không có sidecar |
| Cặp ảnh crop/transcript nhận dạng chữ | 6.585 cặp riêng: 5.285 train và 1.300 val nguồn; chưa có liên kết parent receipt/KIE được xác minh |
| Chia nội bộ hóa đơn | 904 `internal_train`, 231 `internal_dev`, 20 `excluded_duplicate_of_official_validation`, 391 `official_validation_inventory` |

Ảnh gốc nằm ở `data/mcocr/train_images/train_images/` và `val_images/val_images/`; nhãn KIE ở `mcocr_train_df.csv`; sidecar OCR ở `kie_data/kie_data/boxes_and_transcripts/`. `data/processed/manifest.jsonl` lưu ID ổn định, đường dẫn tương đối, nguồn annotation, trạng thái thiếu/lỗi và split. Cặp nhận dạng chữ nằm trong `recognition_manifest.jsonl`; số cặp bằng số vùng KIE là sự trùng hợp về số lượng, không chứng minh hai tập là một.

Quy ước nhãn thực tế được kiểm tra với `loader.FIELD_MAPPING`:

| Nhãn nguồn → trường chuẩn | Số vùng train | Ảnh train có nhãn | Ảnh train không có annotation trường |
|---|---:|---:|---:|
| `SELLER` → `seller_name` | 1.171 | 1.071 | 84 |
| `ADDRESS` → `seller_address` | 1.952 | 1.077 | 78 |
| `TIMESTAMP` → `transaction_datetime` | 1.347 | 1.088 | 67 |
| `TOTAL_COST` → `total_amount` | 2.114 | 1.081 | 74 |
| `TOTAL_TOTAL_COST` → chưa ánh xạ | 1 | Không ép vào trường chuẩn | Không suy ra trường vắng mặt |

Các cột đếm ảnh không cộng với số vùng. Mỗi trường còn có 391 bản ghi validation thiếu ground truth KIE. Có 947/1.155 ảnh train được gán đủ bốn loại trường; 208 ảnh còn lại **không đồng nghĩa** với 208 ảnh thiếu annotation có lỗi. Hai ảnh có mảng KIE rỗng; không có chênh lệch độ dài các mảng nguồn còn lại.

[Trang tác vụ chính thức](https://www.rivf2021-mc-ocr.vietnlp.com/) cho phép ảnh không có đủ trường hoặc có dòng không đọc được. [Trang định dạng dữ liệu](https://www.rivf2021-mc-ocr.vietnlp.com/dataset) mô tả ảnh, polygon và CSV; ví dụ warm-up có cách viết nhãn khác bản cục bộ. Dự án dùng `ADDRESS`/`TIMESTAMP` đã quan sát, không tự đổi theo tên `SELLER_ADDRESS` hoặc ví dụ `TIMESTAMPS` trên website. Không tìm thấy hướng dẫn chi tiết riêng cho báo cáo Z/phiếu bếp trong các trang này; vì thế các ca đó vẫn có bất định về ngữ nghĩa KIE. Không có README/hướng dẫn annotation riêng trong bản dataset cục bộ đã tìm kiếm.

### 2. Kết quả EDA đã tính lại

Số vùng KIE trên một ảnh train: nhỏ nhất **0**, Q1 **5**, trung vị **5**, Q3 **7**, lớn nhất **29**, trung bình **5,7013**. Hai ảnh có 21 và 29 vùng cho thấy cần kiểm tra cả việc gán nhãn quá mức, không chỉ trường thiếu.

| Chỉ số ảnh train | Nhỏ nhất | Trung vị | Lớn nhất |
|---|---:|---:|---:|
| Chiều rộng (pixel) | 352 | 768 | 1.024 |
| Chiều cao (pixel) | 480 | 1.024 | 2.860 |
| Tỷ lệ rộng/cao | 0,2476 | 0,7500 | 1,7778 |
| Độ sáng trung bình ảnh xám | 69,3267 | 133,0371 | 224,6197 |
| Độ tương phản, độ lệch chuẩn ảnh xám | 14,0370 | 39,5171 | 85,9794 |
| Phương sai Laplacian | 22,9347 | 918,3987 | 4.827,2302 |

Đây là thống kê từng đại lượng độc lập, không phải mọi ảnh đều có kích thước trung vị 768×1.024. Có 56 ảnh ngang và 1.099 ảnh dọc/vuông theo kích thước. Trên 1.151 ảnh có sidecar, trung vị theo tập của góc cạnh chữ tuyệt đối trung vị từng ảnh là 0,8185°, lớn nhất 90°. Góc này chỉ là heuristic phụ thuộc hướng cạnh polygon, không xác nhận tự động ảnh đang đọc đúng chiều. Độ sáng, tương phản và Laplacian cũng không phải điểm chất lượng có ground truth; ảnh đã được xoay/phóng lớn khi review nếu cần.

Kiểm tra hình học bằng `validate_polygon()` xác nhận:

- KIE: **6 vùng trên 6 ảnh** có tự giao/chạm cạnh không kề; bốn vùng trong số đó còn có đỉnh lặp. Không có KIE vượt biên ảnh trong manifest hiện tại.
- Transcript toàn trang: **425 vùng trên 109 ảnh** vượt biên ảnh. Đây là lỗi annotation nguồn OCR GT, không phải box do Tesseract dự đoán.
- Tổng cộng 115 bản ghi hóa đơn có lỗi geometry trong export này. Các loại lỗi của cùng vùng có thể chồng lấp.
- `validate_manifest()` vẫn PASS về cấu trúc, ID, đường dẫn và rò rỉ trùng chính xác. PASS cấu trúc không chứng nhận nhãn/text/polygon đúng với pixel.

Đã đọc và giải mã **8.131/8.131 bản ghi ảnh** hóa đơn/crop; kích thước và SHA-256 đều khớp manifest. Đối chiếu toàn bộ **6.585 vùng KIE** với CSV nguồn không thấy thay đổi nhãn, text hoặc tọa độ khi chuẩn hóa. Sáu polygon sai vị trí được phát hiện trực quan trong mẫu là vấn đề khác với sáu polygon sai cấu trúc hình học trên toàn tập; không gộp hai số sáu thành một danh sách.

### 3. Trùng chính xác và nghi gần trùng

Trong train có **31 nhóm SHA-256 trùng**, chứa **64 bản ghi**. Hai mươi bản ghi train trùng ảnh validation chính thức đã được cách ly; kiểm tra trên các split hoạt động và manifest kết hợp hóa đơn/crop không thấy nhóm trùng chính xác đi qua split.

Đã chạy lại `audit_near_duplicates(records, root, threshold=6)` trong bộ nhớ, không ghi lại output: **1.526 ảnh** được băm, **0 ảnh lỗi đọc**, kết quả và danh sách ID/đường dẫn/khoảng cách khớp hoàn toàn artifact hiện có. Có **36 cặp ứng viên**: 10 train/dev, 22 train/validation chính thức, 4 dev/validation chính thức. Số so sánh tương ứng là 208.824, 353.464 và 90.321.

**36 cặp này chưa được phân xử danh tính giao dịch.** pHash 63 bit có thể khớp bố cục chung và có thể bỏ sót khi xoay/cắt mạnh. Kết quả đủ để ghi nhận rủi ro của Goal 1; trước khi cố định benchmark hoặc tuyên bố không có leakage gần trùng, cần xem từng cặp và lập quyết định riêng. Task này không mở rộng mẫu, thay split hoặc tự loại ảnh.

### 4. Audit chất lượng annotation của 40 ảnh

Mẫu do `select_annotation_audit_sample()` chọn từ nguồn train, seed 42, không hoàn lại. Hàm trộn xác định trong các tầng chồng lấp, ưu tiên tầng ít phần tử rồi chọn luân phiên. Các tầng gồm cảnh báo KIE/OCR geometry, nhãn chưa ánh xạ, mảng KIE rỗng, thiếu OCR GT, tứ phân vị thấp/cao của độ nét, độ phủ trường và mật độ vùng. Đã tính lại đặc trưng ảnh và tái tạo đúng **40 ID, thứ tự và lý do chọn** trong `annotation_sample.jsonl`.

Mẫu có 174 vùng KIE; gồm 10 ảnh có cảnh báo geometry KIE/OCR, một nhãn chưa ánh xạ, hai mảng rỗng, bốn ảnh thiếu sidecar, 13 ảnh thuộc tầng nét thấp và chín ảnh thuộc tầng nét cao. Các tầng chồng lấp. Đây là mẫu tìm lỗi có chủ đích; **32/40 = 80% không phải ước lượng tỷ lệ lỗi của toàn dataset** và không có khoảng tin cậy quần thể hợp lệ từ thiết kế này.

Quy trình đã hoàn tất: xem pixel ảnh gốc và overlay, so nhãn raw/trường chuẩn/text/vị trí polygon, tìm trường hiện rõ chưa gán, xoay/crop/phóng lớn khi cần, đối chiếu annotation nguồn. Tái kiểm cuối tập trung sáu ảnh `uncertain=yes` và năm ca chỉ sai transcript; không làm lại hay bỏ lượt review 40 ảnh đã có.

Nguồn kết quả hiện hành duy nhất: `outputs/audit/week1/annotation_review.csv`. File giữ nguyên 40 ID/thứ tự, 13 cột, reviewer Minh Nguyễn và ngày 2026-10-28; có 40 nhận xét tiếng Việt khác nhau. Đã bổ sung bằng chứng tái kiểm vào sáu dòng bất định, **không thay quyết định hoặc cờ phân loại**.

| Đánh giá tổng thể cuối | Số ảnh |
|---|---:|
| `reviewed` | 40/40 |
| `correct` | 6 |
| `incorrect` | 32 |
| `uncertain` | 2 |
| Chưa review | 0 |

| Cờ đánh giá | `yes` | `uncertain` | Diễn giải |
|---|---:|---:|---|
| `wrong_label` | 8 | 2 | Nhãn sai nghĩa; hai ca chưa rõ quy tắc cho báo cáo Z |
| `wrong_geometry` | 6 | 0 | Vùng quá nhỏ/chỉ bao mảnh tên hoặc nằm ngoài tên |
| `missing_field_annotation` | 21 | 5 | Chỉ xác nhận khi trường hiện rõ và liên quan; giữ bất định ở ảnh không đọc được hoặc loại chứng từ chưa có chính sách |
| `unreadable_text` | 3 | 0 | Nhòe, phai hoặc che khuất ảnh hưởng đánh giá |
| `uncertain` | 6 | 0 | Sáu ảnh có ít nhất một phần chưa kết luận; chỉ hai ảnh bất định toàn bộ |

Không cộng các hàng thành số ảnh độc nhất. `incorrect` với ba cờ nhãn/hình học/thiếu đều `no` vẫn hợp lệ nếu có **lỗi transcript** được chỉ rõ; không thêm cột hoặc đổi lỗi chép chữ thành `wrong_label=yes`.

Năm ca chỉ sai transcript đã được xem lại, giữ `incorrect`, `wrong_label=no`, `wrong_geometry=no`, `missing_field_annotation=no`:

| Image ID | Bằng chứng |
|---|---|
| `7c7e572191a3635426719c5f` | `QQNH` trong nguồn, ảnh chỉ có `QNH`; phiếu giao dịch treo không có tổng phải trả |
| `722e66275e9d41f1bd5eb81d` | Nguồn lặp từ trong tiêu đề tổng cộng |
| `c2c26d54d0d0e87addb147a4` | Nguồn cũng lặp từ trong tiêu đề tổng cộng; số tổng được khoanh đúng |
| `e11ba834772075019f08aacd` | Sai dấu tên, thêm chữ vào nhãn ngày và thiếu dấu phân cách phút/giây |
| `84f6e585510121d045f6e0f3` | Sai chữ/dấu tên MINIMART ANAN; không suy ngày giờ bị cắt khỏi ảnh là annotation thiếu |

### 5. Sáu ca bất định sau tái kiểm

| Image ID | Bằng chứng tái kiểm và kết luận giữ lại |
|---|---|
| `37c7371fec6064b857b4fc49` | Nhòe chuyển động toàn ảnh, KIE nguồn rỗng; crop/tăng tương phản không phục hồi được chữ. Giữ overall `uncertain`; chưa xác nhận được trường hiện rõ bị thiếu. |
| `f19ab1e6366ca6617a368607` | Báo cáo Z; transcript/polygon khớp, nhưng tổng phương thức thanh toán khác tổng thanh toán phía trên. Giữ overall `uncertain`; cần quy ước phạm vi và ánh xạ ngày/tổng. |
| `b76c50e8d9a4ea33d09e22a2` | TIMESTAMP đúng; tên/địa chỉ nhìn thấy chưa gán. Nếp gấp che phần có thể chứa tổng, xử lý ảnh không mở được. Giữ `incorrect` và bất định riêng về tổng. |
| `4042bd22a6543500ded1084a` | Phiếu bếp; SELLER bao tiêu đề chức năng, không phải tên nơi bán; ngày giờ phai. Giữ `incorrect`; chưa xác nhận toàn bộ transcript ngày hoặc trường thiếu trong phần không đọc được. |
| `fc4def26d678d4ecf728ac12` | SELLER bao ngày kinh doanh; còn lỗi transcript tiêu đề/số tiền. Giữ `incorrect`; cách ánh xạ trường cho báo cáo Z chưa được hướng dẫn. |
| `a45d3b8c307e428fa84a1b54` | Báo cáo Z; lỗi transcript số tiền được xác nhận. Giữ `incorrect`; không coi ngày hệ thống/tổng báo cáo mặc nhiên là trường giao dịch bán lẻ. |

Các trang chính thức cho phép thiếu trường, nhưng không giải quyết các quy tắc riêng nêu trên. Ghi rõ giới hạn và chuyển sang xử lý theo chính sách là kết quả review hợp lệ; không ép mọi ca thành đúng/sai. Tái kiểm không thay thế việc chủ dự án phân xử trước khi dùng các ca này làm ground truth cuối cùng.

### 6. Phân loại lỗi, ảnh hưởng và cách xử lý tiếp theo

| Nhóm | Số ảnh có bằng chứng trong mẫu | Ví dụ và tác động | Xử lý đề xuất |
|---|---:|---|---|
| A. Nhãn KIE sai | 8 xác nhận; 2 còn bất định | `c0995400b59a5509760f8308`: ngày/giờ gán ADDRESS; `54f2bab2549a079e5ccaf2e2`: tổng tiền gán TIMESTAMP; làm mô hình học sai nghĩa trường | Phân xử rồi sửa trong phiên bản annotation riêng, giữ provenance |
| B. Polygon sai vị trí/phạm vi | 6 | `856a5d0c0770959ea73c7e69`: tam giác vài pixel ngoài tên; bốn phiếu Cô Thỏ chỉ khoanh một mảnh tên; crop huấn luyện/evaluation có thể mất nội dung | Vẽ lại polygon sau xác nhận, không bỏ vùng lỗi âm thầm |
| C. Thiếu annotation mục tiêu | 21 xác nhận; 5 còn bất định | `dee69b5be706d964a7dd15e7`: mảng rỗng dù bốn trường nhìn rõ; gây giám sát thiếu hoặc phạt dự đoán đúng ngoài GT | Bổ sung chỉ khi trường hiện rõ; tách vắng mặt với chưa gán/không đọc được |
| D. Transcript nguồn khác ảnh | Ít nhất 19; trong đó 5 ca chỉ sai transcript | `16be8d1cef9243f2992121c4`: tổng trên ảnh 39.000, nguồn 89.000; lỗi này ảnh hưởng giá trị KIE/CER/WER ngay cả khi nhãn và box đúng | Sửa text trong phiên bản phân xử; giữ cờ nhãn/geometry theo đúng bằng chứng |
| E. Không đọc được/che khuất | 3 | Nhòe ở `37c7371fec6064b857b4fc49`, gấp che ở `b76c50e8d9a4ea33d09e22a2`, phai ở `4042bd22a6543500ded1084a` | Giữ bất định vùng bị ảnh hưởng; cân nhắc thu ảnh khác hoặc loại khỏi đánh giá trường đó bằng chính sách rõ ràng |
| F. Loại chứng từ cần quy ước riêng | 5: 3 báo cáo Z, 2 phiếu bếp | Ba báo cáo Z trong bảng bất định; hai phiếu bếp `4042bd22a6543500ded1084a`, `ac9280a8de4b0d56741af739`; tổng và ngày có ý nghĩa khác giao dịch bán lẻ | Quy định phạm vi hoặc đánh giá riêng; không ép bốn trường. Ba phiếu giao dịch treo trong mẫu cũng không mặc nhiên phải có tổng tiền |
| G. Lỗi tiền xử lý/hiển thị | 0 lỗi được xác nhận trong mẫu | 174 vùng mẫu và toàn bộ 6.585 vùng nguồn khớp manifest; chưa có bằng chứng lỗi phát sinh do biến đổi tọa độ | Giữ so sánh nguồn/chuẩn hóa và kiểm tra overlay; không khái quát thành chứng minh mọi bước xử lý đều hoàn hảo |

Nhóm D được tổng hợp bảo thủ từ các nhận xét chỉ rõ text không khớp ở 19 ảnh, không phải kết quả OCR mới. Danh sách kiểm chứng là: `f54fe04a2b3f06104af4fa27`, `c3abcf9d585488c0afba7e1e`, `54f2bab2549a079e5ccaf2e2`, `9cc123295483b4df598b6eb0`, `a49451acb7d86739edb05460`, `1631d70e78338139050f01c0`, `7c7e572191a3635426719c5f`, `5aadb7193384d3a7ca92457e`, `2d1600de436dac175e296d65`, `722e66275e9d41f1bd5eb81d`, `c2c26d54d0d0e87addb147a4`, `e11ba834772075019f08aacd`, `fc4def26d678d4ecf728ac12`, `a0910a230549ac1b8430fc4c`, `61ec406a409141b0dc53276e`, `a45d3b8c307e428fa84a1b54`, `84f6e585510121d045f6e0f3`, `5b445f44f72c0edb812a93a7`, `16be8d1cef9243f2992121c4`. Không cộng 19 với các nhóm khác để suy số ảnh lỗi.

Rủi ro cần mang sang bước tiếp theo: học sai nhãn/box/text, đánh giá trên GT thiếu, trộn loại chứng từ, coi mẫu tìm lỗi là mẫu đại diện và leakage gần trùng chưa phân xử. Cần chính sách phạm vi, danh sách sửa có phiên bản, ground truth đánh giá được kiểm tra và thiết kế mẫu đại diện nếu muốn đo tỷ lệ lỗi toàn tập. Không relabel, viết lại dataset hoặc thay split trong lần hoàn tất Goal 1 này.

### 7. Kiểm chứng thực thi và tiêu chí hoàn thành

Đã thực hiện ngày 2026-10-28 bằng Python trong `.venv`:

- CSV: đọc UTF-8 nghiêm ngặt và pandas; 40×13, ID/thứ tự khớp mẫu, không trùng, reviewer/ngày/enum/chỉ số vùng/trường đều hợp lệ; 40 ghi chú khác nhau. Không phát hiện mâu thuẫn phân loại cần đổi quyết định. Năm ca `incorrect` chỉ sai transcript đã được giải thích riêng.
- Dữ liệu thật: đối chiếu tất cả 6.585 vùng KIE với raw CSV; tái kiểm geometry KIE/OCR, checksum/kích thước của 8.131 bản ghi ảnh và `validate_manifest()`; tái tạo chính xác mẫu audit và danh sách ứng viên pHash bằng API trong bộ nhớ.
- CLI: `scripts/audit_dataset.py --help` và `scripts/prepare_dataset.py --help` thành công. Đã đọc hành vi ghi file trước khi kiểm tra; không chạy lại chế độ sinh worksheet lên file review hiện hữu.
- Unit tests: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` → **60 passed, 0 failed**.
- Notebook: thực thi trong bộ nhớ bằng `nbclient.NotebookClient` → notebook 01 và 02 **đều PASS, mỗi notebook 7 code cells**. Không lưu thay đổi vào notebook gốc. Jupyter phát cảnh báo runtime/transport trên Windows; không có cell lỗi.
- Không bỏ qua kiểm tra Goal 1 nào vì thiếu dependency hoặc dữ liệu. Phân xử 36 cặp gần trùng và quyết định chính sách cho loại chứng từ chưa thực hiện; chúng là giới hạn được ghi nhận, không phải kiểm tra đã PASS về danh tính giao dịch. Không chạy lại OCR/model/benchmark Goal 3.

Các API tái lập thống kê đã có sẵn: `load_kie_records`, `collect_image_features`, `summarize_field_missingness`, `select_annotation_audit_sample(size=40, seed=42)`, `validate_polygon`, `validate_manifest` và `audit_near_duplicates(threshold=6)`. Các notebook 01/02 cung cấp EDA và biểu đồ tương ứng. `annotations.html`, `annotation_sample.jsonl` và `audit_summary.json` là artifact lúc sinh mẫu: các chữ “pending”/`not_reviewed`/`human_review_status=not_performed` ở đó không tự cập nhật khi CSV được review. Trạng thái review cuối phải lấy từ CSV; không dùng metadata cũ để kết luận review chưa làm.

| Tiêu chí nghiệm thu Goal 1 | Trạng thái | Bằng chứng |
|---|---|---|
| Hiểu nguồn, cấu trúc, đơn vị đếm và schema | PASS | Kiểm tra raw CSV, manifest, ánh xạ nhãn và tài liệu chính thức |
| EDA tái lập hoặc nêu rõ giới hạn | PASS | Đặc trưng ảnh tính lại; notebook 01/02 chạy được |
| Audit 40 ảnh hoàn tất và nhất quán | PASS | 40/40 reviewed, CSV hợp lệ, giữ nguyên mẫu |
| Phân loại vấn đề chất lượng quan trọng | PASS | Nhóm A–G; tách transcript với nhãn/geometry và OCR predictions |
| Bất định được xử lý hoặc ghi rõ | PASS | Tái kiểm sáu ca; ghi đúng phần chưa xác định, không ép kết luận |
| Số liệu thống nhất với nguồn | PASS | Đếm lại manifest/raw/CSV; tái tạo mẫu và ứng viên gần trùng |
| Tests và kiểm tra thích hợp đã chạy | PASS | 60/60 tests, hai notebook, các kiểm tra dữ liệu thật |
| Báo cáo Goal 1 hoàn chỉnh | PASS | Mục này và `ANNOTATION_AUDIT.md` cập nhật kết quả cuối |
| Bảo toàn dữ liệu và công việc có sẵn | PASS | Chỉ sửa hai tài liệu và ghi chú sáu dòng CSV; không sửa raw/manifest/split/notebook |

**Goal 1 đã hoàn thành và sẵn sàng chuyển sang Goal 2.** Độ sạch toàn bộ dataset, 36 quyết định gần trùng và chính sách phân xử cuối vẫn là công việc tiếp theo; PASS này không xác nhận các annotation còn lỗi đã được sửa.

## Goal 2 — Reproducible processing

The preparation CLI produces 1,546 receipt records and 6,585 **separate text-recognition crop/transcript records** (5,285 source train and 1,300 source validation). The latter are loaded from the official recognition text files, not cropped from KIE polygons. The fact that KIE also has 6,585 annotated regions does not establish a parent/field relationship. Internal receipt split counts are 904 train and 231 development records; 20 exact duplicates of official validation are quarantined. Duplicate-aware splitting leaves no exact duplicate groups crossing active splits. Repeated preparation runs produced identical manifest hashes. Notebook 03 visually compares source and normalized annotations and checks split integrity.

### Goal 2 hardening verification — 2026-10-28

Baseline HEAD: `698ddcc03e192d90781ac7e74ceea5883eb5016a`. The working tree initially contained only existing edits to notebooks 01/02; those were preserved. Baseline: **60 tests passed**. The default uv cache was not writable in the sandbox, so verification used a workspace-local `UV_CACHE_DIR`; dependencies and the CI workflow were unchanged.

Confirmed defects were reproduced before fixes: CLI `fail` reported the internal `report` policy; failed preparation could overwrite the successful validation report or leave partially replaced artifacts; structural validation accepted incorrect label/split/geometry/bbox metadata and rejected legacy schema 1.0 blank-text states; `skip` left duplicate/quarantine totals describing removed source records. These were corrected in `preprocessing.py`, `validation.py` and `scripts/prepare_dataset.py`, without changing source annotations, schema versions, the splitting algorithm or assignments. Source/output statistics now have separate scopes. Unknown labels remain unmapped, and properly documented invalid polygons with null bboxes remain structurally valid.

All four artifacts are staged, serialized and verified before replacement. Existing artifacts are backed up for ordinary replacement-error rollback, and the success report is published last. A policy/structural rejection writes a separate `validation_failure_report.json`; it preserves all four previous success files. `--verify-only` checks payload SHA-256 hashes, strict JSON, structural/leakage validation, split summary and output statistics. Details and process/power-loss/concurrency limitations are documented in `DATA_SCHEMA.md` and `WEEK2_HANDOFF.md`.

Final synthetic suite: `uv run python -m pytest -q -p no:cacheprovider` → **104 passed, 0 failed**. The 44 added cases cover policy acceptance/rejection, complete diagnostics and requested policy, source/output counts, unknown labels, geometry/bbox/aggregate issues, KIE/OCR/recognition/inventory separation, schema 1.0 compatibility, source preservation, recognition exact-duplicate quarantine, deterministic four-file output, nonfinite geometry serialization, corrupted/mixed artifacts, serialization failure, replacement failure at each of the four publication steps, and rollback without an existing bundle. Existing splitting tests also pass for empty input, a single group, missing checksums, invalid fractions and seed/input-order determinism. CI continues to use synthetic fixtures without MC-OCR.

Real MC-OCR preparation was run twice into separate private directories `outputs/audit/goal2_hardening_20261028/run_a` and `run_b`, with seed 42, validation fraction 0.2 and policy `report`. All four artifacts are byte-identical between runs:

| Artifact | SHA-256 in both runs |
|---|---|
| `manifest.jsonl` | `bfc183cebe9595cba03e54209b18b2f3fddfc5223675ebbacc70b6dd3010d56c` |
| `recognition_manifest.jsonl` | `159f17911783b6465f9b5ffd37de97d4a086722446aac05baf38e3997f8abf87` |
| `validation_report.json` | `1e6ffa876096befd1212a16146e809b75fcec526bde77e15b111eeb262d83fbb` |
| `split_summary.json` | `b3d1e3062e17a81c2979316aa99967aa621149f0b7cb3b321f7b6955a7e12406` |

The two manifests are also byte-identical to the existing `data/processed/` manifests: every ID, annotation, provenance field and split assignment is preserved. The split summary has identical parsed JSON, but its checksum changes because the old Windows file had 15 CRLF line endings and the new writer uses LF. The validation report checksum changes legitimately because it now includes source/output statistics and artifact hashes and also uses LF. No experimental output was written to `data/processed/`.

Real-data checks: **1,546 receipts**, **6,585 recognition records**, **904 internal_train / 231 internal_dev / 20 quarantined / 391 official inventory**. `validate_manifest()` passes all **8,131 records** with no structural issues or cross-active-split exact duplicates. Direct source comparison preserves all **6,585 KIE regions**, **40,868 full-page OCR regions** (including raw lines/parse diagnostics), and **6,585 crop transcripts/references/line numbers**. The 115 receipt records with source-quality errors remain reported, not cleaned; recognition has zero invalid records.

Real `skip` removes exactly those **115 receipts**, retains all **6,585 crops** and all **391 official inventory rows**, and produces **813 train / 208 dev / 19 quarantine / 391 inventory = 1,431 receipts**. Retained records are identical to their `report` counterparts. Output exact-duplicate groups are **28**, versus **31** in source statistics. Real `fail` returns **exit code 2**, reports requested policy `fail` and **115 receipt / 0 recognition errors**, and preserves all four existing output checksums. Both success bundles and the skip bundle pass `--verify-only`. Private evidence and the source-comparison script are in `outputs/audit/goal2_hardening_20261028/verification.json` and `verify_real_data.py`.

**Goal 2: PASS for the requested hardening.** No confirmed serious in-scope bug remains. Documented limits remain: publication is not atomic across all four files under process/power loss or persistent rollback I/O failures; concurrent writers are unsupported; missing checksums cannot establish identity; source annotation errors, unadjudicated near-duplicates and the absent crop-to-receipt relationship remain. No annotation review, near-duplicate adjudication, model work, dependency change, commit or push was performed.

## Goal 3 — OCR baseline and error analysis

The measurements below are the previously reported baseline, not rerun during the 2026-10-28 Goal 1/2 audit. OCR code, model, predictions and benchmark are unchanged. New geometry findings in that audit concern KIE polygons; the 425 OCR out-of-bounds regions remain unchanged.

The baseline is Tesseract 5.3.4, CPU, Vietnamese `vie` LSTM model from `tesseract-ocr/tessdata_fast` revision `87416418657359cb625c412a48b6e1d6d41c29bd` (SHA-256 `79df64caf7bcfb2a27df5042ecb6121e196eada34da774995747636d5bfa1`). It uses PSM 6, OEM 1 and TSV word boxes. On `internal_dev`, inference succeeded on 231/231 images and emitted 29,849 parsed word boxes; mean latency was 0.500 seconds per image on the recorded 20-logical-CPU host.

Transcription evaluation used 8,304 valid GT regions from 231 images and excluded 104 regions with invalid geometry. Micro CER was 1.8965 and WER was 2.1795 under the alignment and normalization policy in `DATA_SCHEMA.md`. 1,643 GT regions had no assigned prediction; 12,913 predicted word boxes were outside valid GT polygons. These error rates exceed 1 because insertions are counted and the pairing has substantial coverage/alignment mismatch. They are protocol-specific diagnostic values, not a comparable benchmark score. Detection precision/recall/F1 is N/A because GT region polygons and predicted word boxes have incompatible granularity. Unassigned boxes and GT regions without assigned boxes are diagnostic counts, not confirmed false positives or OCR misses; annotation coverage, geometry and alignment need visual review. Notebook 04 shows local overlays and error distributions; it separates OCR quality from the unimplemented KIE task. See `GOAL3_OCR_BASELINE.md` for the full flow and limitations.

A TSV parsing issue was found during evaluation: Tesseract can emit literal tabs/newlines in recognized text, which caused continuation fragments to be interpreted as huge text tokens. The parser now validates the fixed numeric geometry prefix and ignores malformed continuation rows. The full development predictions were regenerated after the fix; maximum parsed text field length was 44 characters.

## Reproduction commands

```bash
uv sync --all-extras
uv run python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir data/processed --seed 42 --validation-fraction 0.2
uv run python scripts/download_ocr_model.py
uv run python scripts/run_ocr.py --split internal_dev --limit 3 --output-dir outputs/ocr/smoke
uv run python scripts/run_ocr.py --split internal_dev --output-dir outputs/ocr/tesseract_internal_dev
uv run python scripts/evaluate_ocr.py --split internal_dev --output-dir outputs/ocr/evaluation
uv run jupyter lab
uv run pytest
```

Execute notebooks 01 through 04 from the repository root after generating their required manifests and predictions. All data, model files, plots, images, and per-image evaluation artifacts remain local and ignored.

Exact notebook execution commands used during final validation:

```bash
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_dataset_audit.ipynb
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/02_exploratory_data_analysis.ipynb
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/03_preprocessing_validation.ipynb
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/04_ocr_baseline_evaluation.ipynb
```

The original implementation reported `uv run pytest -q` (24 passed), all four original script `--help` commands, Python imports through the test suite, and negative CLI checks for missing input files. It reported execution of all four notebooks, followed by output stripping. These are historical validation claims; the independently executed re-audit below supersedes the Goal 1/2 evidence.

## Nhật ký tái kiểm kỹ thuật — 2026-10-28

Phần dưới bảo lưu bằng chứng kỹ thuật và kết quả của các giai đoạn trước trong ngày, gồm cả Goal 2/Goal 3. Những nhận định “chưa có kết quả review” ở nhật ký ban đầu chỉ mô tả thời điểm trước khi hoàn tất worksheet; số liệu và nghiệm thu Goal 1 hiện hành nằm ở phần đầu báo cáo.

Starting state: branch `main`, commit `2955a891a31fec18ee8a6633855ef984bdb020f3`. Notebooks 01/02 already had local modifications and `Untitled.ipynb` was untracked; those files were preserved. No commit or push was performed. Python 3.12.16 and the existing environment were used; baseline tests independently passed 24/24 (with a pre-existing pytest-cache permission warning). Final tests use an ignored output cache.

### Pre-execution verification

| Finding | Conclusion and evidence | Severity | Action |
|---|---|---|---|
| Recognition manifest described as KIE crops | CONFIRMED: `prepare_records()` calls `load_text_recognition_pairs()`; schema/handoff claimed parent IDs and polygons that did not exist | High | Correct schema, report, handoff and README |
| Confused counts | CONFIRMED semantic error: independent sources each contain 6,585 rows/regions | Medium | Distinguish KIE regions from recognition pairs |
| Missing group-key fallback | CONFIRMED: five records without `image_group_id` raise `KeyError`; with `None`, all five incorrectly become train | High | Reuse the grouping key during assignment; regression tests |
| SHA-only duplicate audit | CONFIRMED: `splitting.py` checks SHA-256 groups; existing quarantine works; no perceptual audit existed | Medium | Add optional candidate-only DCT pHash utility |
| No systematic qualitative audit | PARTIALLY CONFIRMED: notebooks had a four-image sample and feature-extreme galleries, but no stratified worksheet/protocol | Medium | Seeded 40-image pack and human review protocol |
| `SELLER_ADDRESS` label | CONFIRMED in `idea.md`; CSV/config/loader use `ADDRESS` | Low | Correct brief |
| Unclear annotation validation states | PARTIALLY CONFIRMED: missingness/geometry states existed, but empty text, raw parse errors, repeated IDs and path checks were incomplete | High | Preserve provenance, add explicit diagnostics and schema 1.1 |

Additional verified defects: `validate_manifest()` accepted an empty ID and `C:/private/a.jpg`; `validate_polygon()` accepted the nonzero-area crossing polygon `[[0,0],[6,5],[0,4],[4,0]]`. `source_by_name` overwrote repeated KIE CSV IDs. These now have regression coverage. Official inventory rows previously lacked `schema_version`; all generated subsets now declare 1.1.

### Independently recomputed data statistics

The local dataset exists and was read directly. There are 1,155 train images, 391 official validation images, 1,546 receipt manifest rows, and 6,585 recognition pairs. All 8,131 image records decode successfully. No recognition crops are missing; all 6,585 recognition transcripts are nonblank. The validation sample CSV has `img_id`, `anno_image_quality`, `anno_texts`, and **no KIE label/polygon columns**. It cannot establish KIE ground truth.

| KIE label | Regions | Train images with label | Train images without label annotation |
|---|---:|---:|---:|
| SELLER | 1,171 | 1,071 | 84 |
| ADDRESS | 1,952 | 1,077 | 78 |
| TIMESTAMP | 1,347 | 1,088 | 67 |
| TOTAL_COST | 2,114 | 1,081 | 74 |
| TOTAL_TOTAL_COST (unmapped) | 1 | Not mapped to a target field | Not inferred |

Two train rows have empty annotation arrays; array lengths otherwise agree. No-label counts do not prove field absence. For each field, 391 additional official-validation records have unavailable KIE ground truth. No field-absence judgment or human annotation-correctness result is claimed.

Full-page transcription sidecars cover 1,151 train images and contain 40,868 regions; four images lack a sidecar. The strengthened geometry audit finds:

- 425 out-of-bounds OCR regions across 109 images, unchanged from the original report.
- Six invalid KIE regions across six other images with nonadjacent edge intersections/touches, including four with repeated vertices. These affect three SELLER and three ADDRESS regions. They were missed by the old area/bounds-only check.
- 115 receipt records with image/geometry/structural errors in total (all caused by geometry in this export). All are retained under default `report`; derived bboxes for invalid regions are null. Issue categories overlap, so 425 + 4 + 6 is not a count of distinct bad regions.

### Duplicate and annotation audit outputs

Exact source-train duplicate statistics remain 31 groups / 64 records. Twenty groups matching official validation are quarantined. Active splits have zero exact-duplicate leakage, including the combined receipt/recognition manifest check. Receipt IDs and every existing receipt split assignment match the pre-change manifest exactly: **904 train / 231 dev / 20 quarantine / 391 official inventory**.

The optional 63-bit DCT pHash audit, threshold 6, hashed 1,526 nonquarantined receipt images with zero read failures. It compared 208,824 train/dev pairs, 353,464 train/official-validation pairs and 90,321 dev/official-validation pairs. It found **36 candidates**: 10 train/dev, 22 train/official validation, 4 dev/official validation. These are unreviewed similarities, not confirmed duplicate transactions; common layouts can match. No split was changed.

Mẫu seed 42 có 40 ảnh train khác nhau và 40 overlay KIE. Các tầng chồng lấp gồm 10 ca cảnh báo geometry, một nhãn chưa ánh xạ, hai mảng rỗng, bốn ảnh thiếu sidecar, 13 ca nét thấp và chín ca nét cao. Khi sinh mẫu, worksheet có trạng thái `not_reviewed`; đến cuối ngày 2026-10-28, cả 40 dòng đã `reviewed`, kết quả 32 sai / 6 đúng / 2 bất định. Chi tiết cuối cùng nằm ở phần Goal 1 và [ANNOTATION_AUDIT.md](ANNOTATION_AUDIT.md); metadata tự động lúc sinh mẫu vẫn được giữ như artifact lịch sử.

Private artifacts: `outputs/audit/week1/{annotations.html,annotation_review.csv,annotation_sample.jsonl,near_duplicates.html,near_duplicate_candidates.jsonl,near_duplicate_summary.json,audit_summary.json}`. Opening or editing these locally does not publish them. The CLI's refusal to overwrite an existing worksheet was tested: exit 2, worksheet SHA-256 unchanged.

### Test and reproducibility evidence

Final suite: **60 passed, 0 failed** with `.venv\Scripts\python.exe -m pytest -q -o cache_dir=outputs/audit/pytest_cache`. New synthetic tests cover missing checksums, duplicate/single groups, invalid fractions, seed/order determinism, quarantine, malformed/empty sidecars, invalid IDs/paths, repeated source rows, corruption/missing images, strict JSON for nonfinite values, recognition provenance, field missingness, stratified selection and resize/JPEG perceptual candidates.

Real-data commands (repository root; `uv run python` is equivalent to the existing venv executable used here):

```bash
python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir data/processed --seed 42 --validation-fraction 0.2
python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir outputs/audit/repeat_preparation --seed 42 --validation-fraction 0.2
python scripts/audit_dataset.py --dataset-root data/mcocr --output-dir outputs/audit/week1 --seed 42 --sample-size 40 --threshold 6
```

Both manifests, `validation_report.json`, and `split_summary.json` are byte-identical across repeated preparations. Manifest SHA-256 values:

| File | SHA-256 |
|---|---|
| `manifest.jsonl` | `bfc183cebe9595cba03e54209b18b2f3fddfc5223675ebbacc70b6dd3010d56c` |
| `recognition_manifest.jsonl` | `159f17911783b6465f9b5ffd37de97d4a086722446aac05baf38e3997f8abf87` |

`validate_manifest()` passes all 8,131 records, separately from the 115 source-quality findings. All five script `--help` commands return 0. Seven negative CLI checks (missing dataset/manifest, invalid fraction/threshold/sample size, OCR/evaluation missing manifest) return 2 without tracebacks. No OCR model download or benchmark was run.

Notebooks 01, 02 and 03 execute successfully via `nbclient.NotebookClient`, using the local dataset and generated manifests. Executed copies are under ignored `outputs/audit/notebooks/`; source notebook outputs are not populated. Notebook 03's conclusion was corrected for the new KIE geometry findings. Notebook 04 was not executed in this task because Goal 3 is unchanged. Windows Jupyter emitted event-loop/profile permission warnings during initial execution, but no notebook cell failed.

### Readiness and remaining risks

- **Goal 1: PASS sau lần hoàn tất ngày 2026-10-28.** Đã kiểm tra dữ liệu/EDA, review 40 ảnh, tái kiểm bất định và hoàn chỉnh báo cáo. Danh tính giao dịch của 36 cặp nghi gần trùng chưa được phân xử; giới hạn này được ghi rõ, không suy thành không có leakage.
- **Goal 2: PASS for the requested engineering work.** Preparation, source preservation, structural validation, deterministic splits and exact-duplicate quarantine have real-data and synthetic-test evidence. This is not a claim that the source annotations are error-free or that all near-duplicate leakage has been ruled out.
- **Goal 3: UNCHANGED.** Existing OCR tests pass, but no new OCR/KIE training, inference or benchmark result is claimed.

Audit trực quan 40 ảnh đã hoàn tất; sáu ảnh còn phần bất định được mô tả cụ thể ở Goal 1. Cần phân xử 36 cặp nghi gần trùng trước khi tuyên bố benchmark không rò rỉ; pHash có thể báo nhầm/bỏ sót và thuật toán hiện tại so sánh bậc hai. Liên kết parent receipt của cặp nhận dạng chữ vẫn chưa có; validation chính thức thiếu KIE GT. Những giới hạn này được chuyển sang xử lý tiếp theo, không che giấu bằng kết luận PASS của phần hiểu dữ liệu.

## Blockers and Week 2 readiness

Week 2 can import normalized records, split assignments, OCR predictions and reusable metrics directly from the documented Python modules/JSONL files; no notebook execution is required. The main evaluation limitation is the mismatch between word-level predictions and coarser GT regions, which makes CER/WER alignment-sensitive and detection F1 unavailable. KIE training and field extraction remain intentionally unimplemented. MC-OCR redistribution terms were not available in the local project files; no dataset assets are included, and the terms must be confirmed before redistribution.

## Phase commits

| Phase | Status | Commit |
|---|---|---|
| 0 | PASS | `c6c68bfc4cb960dbb64a08b3d9e3530c483bfb36` |
| 1 | PASS | `f52c02de328982e19e2b3e403cdbd72dfa433ec1` |
| 2 | PASS | `20641efb3b4394601813887f004d4869dcf048eb` |
| 3 | PASS | `67f0d3df7862a86c18317d72e300edf8f4ecda0a` |
| 4 | PASS | `24e6250f693741ee60210b2e9ada084e12b2dcd0` |
| 5 | PASS | `bca1ad000d0d0ef1f2006c899e45b543145155a8` |
| 6 | PASS | `ef7e2cf4e7979ced7ace53e9989823763c4cbf7d` |
| 7 | PASS | `c04cfa497d4baf4b903650f3c6c2c5e8dd7283b2` |
