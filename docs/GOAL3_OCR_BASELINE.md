# Goal 3 — OCR baseline và phân tích lỗi

Goal 3 đo một **OCR baseline** trên ảnh biên lai và khảo sát nơi phép đo gặp vấn đề. Nó chưa trích xuất bốn trường KIE (`SELLER`, `ADDRESS`, `TIMESTAMP`, `TOTAL_COST`) và chưa có điểm đánh giá KIE.

## Luồng chạy

```text
Ảnh + manifest (internal_dev)
    │
    ├─ run_ocr.py → TesseractBaseline → predictions.jsonl + failures.jsonl + runtime.json
    │                 (chữ, box từng từ, confidence)
    │
    └─ OCR transcript GT (ocr_regions trong manifest)
                      │
                      └─ evaluate_ocr.py → metrics.json
                                           per_image_metrics.jsonl
                                           per_region_alignment.jsonl
                                           │
                                           └─ notebook 04: biểu đồ, overlay và xem ca lỗi
```

1. `scripts/prepare_dataset.py` tạo `data/processed/manifest.jsonl`. Mỗi ảnh có `split`; một phần ảnh train có `ocr_regions` từ sidecar transcript toàn trang. Các vùng này khác nhãn KIE trong `regions`. `internal_dev` là tập dev nội bộ, không phải official validation.
2. `scripts/download_ocr_model.py` tải `vie.traineddata` đã pin revision và kiểm SHA-256. `scripts/run_ocr.py` đọc các ảnh trong split, sắp theo `image_id` rồi gọi `TesseractBaseline.predict()` cho từng ảnh. Baseline dùng Tesseract CPU, ngôn ngữ `vie`, PSM 6, OEM 1 và xuất TSV. Parser giữ hàng word box, chữ, polygon chữ nhật và confidence từ 0 đến 1. Lỗi đọc/chạy OCR được ghi riêng trong `failures.jsonl`.
3. `scripts/evaluate_ocr.py` ghép prediction theo `image_id` với manifest. Ảnh có transcript GT phải có một prediction thành công; thiếu hoặc lỗi thì evaluation dừng. Một prediction thành công với 0 từ vẫn được đánh giá: các vùng GT của ảnh đó có hypothesis rỗng.
4. `evaluate_ocr_records()` chỉ dùng vùng GT có chữ không rỗng và geometry hợp lệ. Với mỗi box từ dự đoán, lấy tâm box; nếu tâm nằm trong nhiều vùng GT, gán vào vùng có diện tích nhỏ nhất. Các từ đã gán được sắp theo tọa độ `y`, rồi `x`, và nối bằng dấu cách. Box không nằm trong vùng GT hợp lệ được đếm là *unassigned*. Vùng GT không nhận box nào được đếm là *unmatched*.
5. Sau chuẩn hóa Unicode NFKC, chữ thường và khoảng trắng, code tính khoảng cách chỉnh sửa cho từng transcript GT so với chuỗi dự đoán đã ghép. CER = tổng lỗi ký tự / tổng ký tự GT; WER = tổng lỗi token / tổng token GT. WER ở đây tách theo khoảng trắng, nên token tiếng Việt thường là **âm tiết**, không phải từ ngữ pháp. Đây là **micro average**: cộng tử số và mẫu số trên tất cả vùng hợp lệ rồi mới chia. Dấu tiếng Việt và dấu câu vẫn được giữ. Giá trị có thể lớn hơn 1 do phép chèn. Vùng GT không nhận box đóng góp lỗi xóa; box *unassigned* chỉ được đếm riêng, không trực tiếp đi vào CER/WER.
6. Notebook `04_ocr_baseline_evaluation.ipynb` đọc artifact cục bộ, vẽ phân bố lỗi và overlay box dự đoán với vùng GT để xem từng ca. Các con số trong notebook lấy từ `metrics.json`, không cố định trong markdown.

## Kết quả đã ghi nhận trên `internal_dev`

Kết quả lịch sử trong `WEEK1_REPORT.md` và artifact local hiện có: Tesseract 5.3.4 chạy thành công trên **231/231 ảnh**, tạo **29.849 word boxes**; thời gian trung bình **0,500 giây/ảnh** trên máy được ghi nhận. Evaluation dùng **8.304 vùng GT hợp lệ**, loại **104 vùng geometry không hợp lệ**. Micro CER **1,8965**, WER **2,1795**. Có **1.643 vùng GT** không được gán box và **12.913 box** không nằm trong vùng GT hợp lệ.

Các số 1.643 và 12.913 là **dấu hiệu cần xem lại**, không tự chứng minh OCR bỏ sót hoặc nhận nhầm chữ. Box unassigned có thể nằm trên chữ chưa được annotation; vùng unmatched có thể do OCR, polygon GT hoặc cách ghép tâm box. CER/WER cũng trộn sai chữ thực sự với sai ghép vùng và sai transcript GT, vì vậy **không nên dùng chúng để so sánh mô hình như benchmark chuẩn**.

Detection precision/recall/F1 là `N/A`: Tesseract tạo box từng từ còn GT toàn trang dùng vùng lớn hơn (dòng/nhóm chữ). Ghép 1:1 theo IoU sẽ đánh đồng cách chia vùng với khả năng phát hiện chữ. Tham số `--iou-threshold` hiện chỉ được ghi trong metadata của trạng thái `N/A`; nó không làm thay đổi CER/WER.

## Chạy lại

Từ thư mục gốc repository, sau khi có dataset và môi trường Python:

```bash
uv run python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir data/processed --seed 42 --validation-fraction 0.2
uv run python scripts/download_ocr_model.py
uv run python scripts/run_ocr.py --split internal_dev --limit 3 --output-dir outputs/ocr/smoke
uv run python scripts/run_ocr.py --split internal_dev --output-dir outputs/ocr/tesseract_internal_dev
uv run python scripts/evaluate_ocr.py --split internal_dev --output-dir outputs/ocr/evaluation
uv run jupyter lab
```

Smoke run 3 ảnh chỉ kiểm tra đường chạy; không dùng file prediction đó để đánh giá toàn bộ split. Dataset, model, predictions, transcript và biểu đồ ở các đường dẫn local bị Git ignore.

## Cần cải thiện trước khi tuyên bố chất lượng OCR

- Xác minh các cặp vùng GT và box dự đoán bằng ảnh thật; phân loại riêng lỗi OCR, lỗi annotation và lỗi ghép. Hiện notebook chỉ giúp quan sát, chưa tạo taxonomy nguyên nhân có nhãn người review.
- Quy định annotation cùng đơn vị với output (word hoặc line), hoặc kiểm chứng một thuật toán gộp box theo dòng. Sau đó mới tính detection F1 hoặc benchmark CER/WER có thể so sánh.
- Khi sang KIE, dùng `regions` và nhãn trường KIE riêng. Không suy ra điểm trích xuất trường từ CER/WER của transcript toàn trang.
