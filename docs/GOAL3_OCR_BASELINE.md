# Goal 3 — OCR baseline và phân tích lỗi

**Đính chính nguồn 05/11/2026:** Parser full-page trước đây đọc nhầm cột nhãn
thành transcript và đã được sửa. Các CER/WER full-page lịch sử bên dưới không dùng để xếp hạng
chất lượng OCR. Xem [phát hiện và phạm vi ảnh hưởng](PSM_COMPARISON_REPORT.md).
Phát hiện này không thuộc parser recognition crop.

**Cập nhật 05/11/2026:** Đã tái chạy clean crop benchmark cho **Week 2 Goal 1**
bằng Tesseract 5.5.3.20260724, có exact-match, coverage và review 24 mẫu. Xem
[báo cáo Week 2](WEEK2_REPORT.md). Các bảng ngày 04/11/2026 bên dưới được giữ
làm kết quả lịch sử của môi trường Tesseract 5.3.4.

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
2. `scripts/download_ocr_model.py` tải `vie.traineddata` đã pin revision và kiểm SHA-256. `scripts/run_ocr.py` đọc các ảnh trong split, sắp theo `image_id` rồi gọi `TesseractBaseline.predict()` cho từng ảnh. Baseline dùng Tesseract CPU, ngôn ngữ `vie`, OEM 1 và xuất TSV. PSM 6 là mặc định; `--psm` cho phép chọn giả định phân đoạn khác và giá trị thực tế được ghi trong `runtime.json`. Parser giữ hàng word box, chữ, polygon chữ nhật và confidence từ 0 đến 1. Lỗi đọc/chạy OCR được ghi riêng trong `failures.jsonl`.
3. `scripts/evaluate_ocr.py` ghép prediction theo `image_id` với manifest. Ảnh có transcript GT phải có một prediction thành công; thiếu hoặc lỗi thì evaluation dừng. Một prediction thành công với 0 từ vẫn được đánh giá: các vùng GT của ảnh đó có hypothesis rỗng.
4. `evaluate_ocr_records()` chỉ dùng vùng GT có chữ không rỗng và geometry hợp lệ. Với mỗi box từ dự đoán, lấy tâm box; nếu tâm nằm trong nhiều vùng GT, gán vào vùng có diện tích nhỏ nhất. Các từ đã gán được sắp theo tọa độ `y`, rồi `x`, và nối bằng dấu cách. Box không nằm trong vùng GT hợp lệ được đếm là *unassigned*. Vùng GT không nhận box nào được đếm là *unmatched*.
5. Sau chuẩn hóa Unicode NFKC, chữ thường và khoảng trắng, code tính khoảng cách chỉnh sửa cho từng transcript GT so với chuỗi dự đoán đã ghép. CER = tổng lỗi ký tự / tổng ký tự GT; WER = tổng lỗi token / tổng token GT. WER ở đây tách theo khoảng trắng, nên token tiếng Việt thường là **âm tiết**, không phải từ ngữ pháp. Đây là **micro average**: cộng tử số và mẫu số trên tất cả vùng hợp lệ rồi mới chia. Dấu tiếng Việt và dấu câu vẫn được giữ. Giá trị có thể lớn hơn 1 do phép chèn. Vùng GT không nhận box đóng góp lỗi xóa; box *unassigned* chỉ được đếm riêng, không trực tiếp đi vào CER/WER.
6. Notebook `04_ocr_baseline_evaluation.ipynb` đọc artifact cục bộ, vẽ phân bố lỗi và overlay box dự đoán với vùng GT để xem từng ca. Các con số trong notebook lấy từ `metrics.json`, không cố định trong markdown.

## Kết quả đã ghi nhận trên `internal_dev`

Kết quả lịch sử trong `WEEK1_REPORT.md` và artifact local hiện có: Tesseract 5.3.4 chạy thành công trên **231/231 ảnh**, tạo **29.849 word boxes**; thời gian trung bình **0,500 giây/ảnh** trên máy được ghi nhận. Evaluation dùng **8.304 vùng GT hợp lệ**, loại **104 vùng geometry không hợp lệ**. Micro CER **1,8965**, WER **2,1795**. Có **1.643 vùng GT** không được gán box và **12.913 box** không nằm trong vùng GT hợp lệ.

Các số 1.643 và 12.913 là **dấu hiệu cần xem lại**, không tự chứng minh OCR bỏ sót hoặc nhận nhầm chữ. Box unassigned có thể nằm trên chữ chưa được annotation; vùng unmatched có thể do OCR, polygon GT hoặc cách ghép tâm box. CER/WER cũng trộn sai chữ thực sự với sai ghép vùng và sai transcript GT, vì vậy **không nên dùng chúng để so sánh mô hình như benchmark chuẩn**.

Evaluator hiện ghi cả mẫu số và tỷ lệ coverage: `unmatched_ground_truth_region_rate` dùng số vùng GT hợp lệ làm mẫu số, còn `unassigned_prediction_word_box_rate` dùng tổng word box dự đoán. Hai tỷ lệ này vẫn là chẩn đoán alignment, không phải recall và false-positive rate của OCR.

Detection precision/recall/F1 là `N/A`: Tesseract tạo box từng từ còn GT toàn trang dùng vùng lớn hơn (dòng/nhóm chữ). Ghép 1:1 theo IoU sẽ đánh đồng cách chia vùng với khả năng phát hiện chữ. Tham số `--iou-threshold` hiện chỉ được ghi trong metadata của trạng thái `N/A`; nó không làm thay đổi CER/WER.

## Baseline crop và so sánh PSM

Lượt chạy ngày 04/11/2026 dùng Tesseract 5.3.4, cùng model SHA-256 `79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1`. Cả 6.585 crop PSM 7 đều inference thành công. Crop evaluator nối các từ theo thứ tự TSV rồi so trực tiếp với transcript, nên không phụ thuộc polygon hoặc thuật toán ghép vùng.

| Split / PSM | Vai trò | Crop | Rỗng | CER | WER |
|---|---|---:|---:|---:|---:|
| `official_val`, PSM 7 | benchmark | 1.300 | 5 | 0,1951 | 0,5549 |
| `official_train`, PSM 7 | diagnostic | 5.285 | 16 | 0,1968 | 0,5607 |
| `official_val`, PSM 6 | compatibility | 1.300 | 8 | 0,2269 | 0,6019 |

Trên cùng validation split, PSM 7 giảm CER khoảng 14% tương đối so với PSM 6. Đây là baseline nhận dạng sạch khỏi lỗi ghép vùng, nhưng vẫn phụ thuộc chất lượng transcript nguồn và cách Tesseract tách/nối từ.

## So sánh ba engine trên `official_val`

Lượt chạy hoàn tất ngày 05/11/2026 dùng đúng 1.300 crop `official_val`, 23.739 ký tự GT và 4.815 token GT cho cả ba engine. VietOCR và PaddleOCR chạy recognition-only trên crop có sẵn; PaddleOCR không chạy detector. Không engine nào có inference failure.

| Engine | Model | Crop rỗng | CER | WER | Giây/crop |
|---|---|---:|---:|---:|---:|
| VietOCR 0.3.13 | `vgg_transformer` | 0 | 0,0959 | 0,3387 | 0,0850 |
| PaddleOCR 3.7.0 | `latin_PP-OCRv5_mobile_rec` | 5 | 0,1744 | 0,6303 | 0,0998 |
| Tesseract 5.3.4, PSM 7 | `vie.traineddata` | 5 | 0,1951 | 0,5549 | 0,0652 |

VietOCR có CER thấp nhất, giảm khoảng 50,8% tương đối so với Tesseract PSM 7. PaddleOCR có CER thấp hơn Tesseract nhưng WER cao hơn, nên không nên kết luận từ một chỉ số duy nhất. Các lượt inference cuối được chạy tuần tự trên CPU sau khi lượt song song gây oversubscription; latency được giữ làm provenance, không dùng để xếp hạng tốc độ vì số thread nội bộ và tải máy chưa được kiểm soát như benchmark hiệu năng.

Checkpoint VietOCR có SHA-256 `380512193a8b6cbf6fad80deacdc9b6939d10d473d199892fc6408d13775ea59`; thư mục model PaddleOCR có digest `0cf4c40d7eaf7eaff0d9042db18a49624d4b57f4a86516a1cb47f8f020c08b8a`; Tesseract dùng hash đã ghi ở phần baseline. Lệnh cài optional dependency, tải model, inference, evaluation và comparison nằm trong [hướng dẫn pipeline](PIPELINE.md). `outputs/ocr/engine_comparison/per_crop_comparison.jsonl` và notebook 04 giữ ba hypothesis để xem các crop bất đồng cục bộ.

So sánh full-page dùng cùng 231 ảnh `internal_dev`, 8.304 vùng GT hợp lệ và không có inference failure:

| PSM | Word box | CER | WER | Unmatched GT | Unassigned box | Giây/ảnh |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 18.629 | 1,8107 | 2,0866 | 33,47% | 19,68% | 0,387 |
| 6 | 29.849 | 1,8965 | 2,1795 | 19,79% | 43,26% | 0,500 |
| 11 | 24.347 | 1,8662 | 2,2242 | 20,45% | 29,12% | 0,471 |

PSM 4 có CER/WER thấp nhất và ít box unassigned nhất, nhưng bỏ unmatched nhiều vùng GT hơn đáng kể. PSM 11 giảm unassigned so với PSM 6 nhưng WER cao hơn. Vì mỗi PSM thay đổi segmentation và số box, bảng này không xác lập một chế độ full-page tốt nhất; cần chọn theo trade-off và kiểm tra ảnh thực tế.

Các lượt so sánh được tạo bằng các lệnh sau; mỗi cấu hình ghi vào một thư mục riêng:

```bash
uv run python scripts/run_ocr.py --manifest data/processed/recognition_manifest.jsonl --split official_train --psm 7 --output-dir outputs/ocr/crop_psm7_official_train
uv run python scripts/evaluate_ocr.py --mode crop --manifest data/processed/recognition_manifest.jsonl --predictions outputs/ocr/crop_psm7_official_train/predictions.jsonl --split official_train --output-dir outputs/ocr/crop_psm7_official_train_evaluation

uv run python scripts/run_ocr.py --manifest data/processed/recognition_manifest.jsonl --split official_val --psm 6 --output-dir outputs/ocr/crop_psm6_official_val
uv run python scripts/evaluate_ocr.py --mode crop --manifest data/processed/recognition_manifest.jsonl --predictions outputs/ocr/crop_psm6_official_val/predictions.jsonl --split official_val --output-dir outputs/ocr/crop_psm6_official_val_evaluation

uv run python scripts/run_ocr.py --split internal_dev --psm 4 --output-dir outputs/ocr/tesseract_internal_dev_psm4
uv run python scripts/evaluate_ocr.py --predictions outputs/ocr/tesseract_internal_dev_psm4/predictions.jsonl --split internal_dev --output-dir outputs/ocr/tesseract_internal_dev_psm4_evaluation

uv run python scripts/run_ocr.py --split internal_dev --psm 11 --output-dir outputs/ocr/tesseract_internal_dev_psm11
uv run python scripts/evaluate_ocr.py --predictions outputs/ocr/tesseract_internal_dev_psm11/predictions.jsonl --split internal_dev --output-dir outputs/ocr/tesseract_internal_dev_psm11_evaluation
```

Các artifact local nằm ở `outputs/ocr/crop_psm7_*`, `outputs/ocr/crop_psm6_official_val*`, `outputs/ocr/tesseract_internal_dev_psm4*`, `outputs/ocr/tesseract_internal_dev_psm6_evaluation`, và `outputs/ocr/tesseract_internal_dev_psm11*`.

## Chạy lại

Các lệnh hiện hành, đầu vào/đầu ra và thứ tự chạy nằm trong [hướng dẫn pipeline](PIPELINE.md). Smoke run ba ảnh chỉ kiểm tra đường chạy; không dùng kết quả đó để đánh giá toàn bộ split. Dataset, model, predictions, transcript và biểu đồ ở các đường dẫn local bị Git ignore.

## Cần cải thiện trước khi tuyên bố chất lượng OCR

- Xác minh các cặp vùng GT và box dự đoán bằng ảnh thật; phân loại riêng lỗi OCR, lỗi annotation và lỗi ghép. Hiện notebook chỉ giúp quan sát, chưa tạo taxonomy nguyên nhân có nhãn người review.
- Quy định annotation cùng đơn vị với output (word hoặc line), hoặc kiểm chứng một thuật toán gộp box theo dòng. Sau đó mới tính detection F1 hoặc benchmark CER/WER có thể so sánh.
- Khi sang KIE, dùng `regions` và nhãn trường KIE riêng. Không suy ra điểm trích xuất trường từ CER/WER của transcript toàn trang.
