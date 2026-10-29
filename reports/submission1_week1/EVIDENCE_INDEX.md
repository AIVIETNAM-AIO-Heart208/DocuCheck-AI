# Danh mục minh chứng — Submission I, Week 1

**Lưu ý phiên bản (29/10/2026):** Đây là hồ sơ kỹ thuật của bản báo cáo 19 trang trước khi biên tập. PDF hiện tại là bản 5 trang dành cho người xem, không dùng mã E01–E15 hoặc phụ lục minh chứng. Số liệu nguồn vẫn có thể được truy vết bằng danh mục dưới đây; các mô tả về bố cục PDF cũ không còn áp dụng.

Mốc kiểm tra: **28/10/2026, Asia/Saigon**. Commit nguồn: `4ee27760ee0cb81f3467a2a20ac484bad7efda5e`.

Mọi đường dẫn dự án dưới đây tính từ gốc repository. Đường dẫn `evidence/`, `figures/` và các tệp báo cáo tính từ thư mục `reports/submission1_week1/` khi được ghi rõ. Mã E01–E15 thuộc hồ sơ kỹ thuật cũ.

**Đã kiểm chứng** chỉ áp dụng cho phép kiểm được mô tả. Đọc lại kết quả review không tương đương review lại pixel; kiểm hai lần chạy có sẵn không tương đương chạy lại preparation. Hồ sơ này không chứa ảnh, transcript, ghi chú biên lai chi tiết hoặc credentials.

| Mã / phạm vi | Claim hoặc deliverable | Nguồn chính | Phép kiểm và trạng thái |
|---|---|---|---|
| E01 / dự án | Commit và các giai đoạn lịch sử | Git HEAD/log; `docs/WEEK1_REPORT.md`; report `evidence/repository_context.json` | HEAD/log đã đọc. Các số 24/60/104 tests là lịch sử theo tài liệu, không chạy các revision cũ. Bốn notebook đã có thay đổi cục bộ; hash workspace nằm trong manifest. |
| E02 / phạm vi | Mục tiêu sản phẩm, giới hạn tuần 1, bàn giao | `README.md`, `docs/idea.md`, `docs/WEEK2_HANDOFF.md` | Đã đọc; KIE, verification, API/UI là định hướng. Handoff nhắc review 40 ảnh còn pending là trạng thái cũ so với CSV hoàn tất. |
| E03 / Goal 1 | 1.546 receipt records; 1.155 train; 391 inventory; 1.491 receipt contents; 1.122 train contents; 6.585 KIE regions; 40.868 OCR regions; 6.585 crops | `data/processed/manifest.jsonl`, `recognition_manifest.jsonl`, `validation_report.json`; `data/mcocr/mcocr_train_df.csv`; `src/docucheck/data/loader.py` | Tái đếm, đối chiếu 6.585 vùng KIE với nhãn/text/tọa độ nguồn; giải mã, kiểm kích thước và hash 8.131 ảnh. Crop recognition độc lập, chưa có parent receipt/KIE được xác minh. |
| E04 / Goal 1 | Phân bố kích thước, tỷ lệ, sáng/tương phản/Laplacian; mẫu audit | `src/docucheck/data/eda.py::collect_image_features`, `select_annotation_audit_sample`; notebooks 01/02 | Tính lại trên 1.155 ảnh train bằng hàm hiện tại; tái tạo đúng ID/thứ tự/lý do của 40 ảnh. Đã tạo hình tổng hợp từ số liệu thật; không tạo ảnh minh họa giả. |
| E05 / Goal 1 | Review 40/40; 6 đúng, 32 sai, 2 bất định; flags 8/6/21/3/6 | `outputs/audit/week1/annotation_review.csv`, `annotation_sample.jsonl`; `docs/ANNOTATION_AUDIT.md` | Tái đếm CSV và đối chiếu mẫu; không review lại mọi pixel. Flags chồng lấp. Metadata `human_review_status=not_performed` ở summary cũ không ghi đè CSV hiện tại. Mẫu ưu tiên rủi ro không đại diện tỷ lệ lỗi quần thể. |
| E06 / Goal 2 | Schema 1.1, provenance, validation, report/skip/fail, staging/rollback | `docs/DATA_SCHEMA.md`; `src/docucheck/data/preprocessing.py::prepare_records`, `_normalize_region`; `validation.py::validate_polygon`, `validate_manifest`; `scripts/prepare_dataset.py::verify_outputs`, `_publish` | Đã đọc mã, kiểm hành vi bằng suite hiện tại. Valid cấu trúc không xác nhận annotation đúng với pixel. Không bảo đảm atomic bốn tệp, power loss, persistent rollback failure hoặc writer đồng thời. |
| E07 / Goal 1–2 | Split 904/231/20/391; 31 nhóm trùng train gồm 64 records; zero active exact crossover | `src/docucheck/data/splitting.py`; `data/processed/split_summary.json`; receipt/crop manifests | Tái đếm nhóm, split và chạy exact-leakage validator trên hai manifest kết hợp. Quarantine bị loại khỏi active split check. SHA-256 không chứng minh không có near-duplicate. |
| E08 / Goal 1 | 36 pHash candidates: 10 train/dev, 22 train/official, 4 dev/official | `outputs/audit/week1/near_duplicate_candidates.jsonl`, `near_duplicate_summary.json`, `near_duplicate_failures.jsonl`; `src/docucheck/data/duplicates.py`; `scripts/audit_dataset.py` | Đã kiểm số dòng/phân nhóm và đọc thuật toán 63-bit DCT, threshold 6. 1.526 ảnh băm và zero lỗi đọc là metadata có sẵn; không tái băm lần này. Chưa có quyết định cùng/khác giao dịch. |
| E09 / Goal 3 | Tesseract CPU vie, PSM 6/OEM 1, model pin, runtime 231 success | `src/docucheck/ocr/baseline.py`, `inference.py`; `scripts/run_ocr.py`, `download_ocr_model.py`; `configs/week1.yaml`, `tesseract_tsv.conf`; `outputs/ocr/tesseract_internal_dev/{runtime.json,predictions.jsonl,failures.jsonl}` | Đọc mã/runtime; 231 success rows và zero failures khớp. Kiểm model SHA-256. Không inference lại. Runtime là 5.5.3.20260724, YAML/lịch sử là 5.3.4. |
| E10 / Goal 3 | 26.859 boxes; CER 1,872454448; WER 2,144846145; 8.304 vùng; 104 geometry loại; 1.886 unmatched; 10.488 unassigned | `outputs/ocr/evaluation/{metrics.json,per_image_metrics.jsonl,per_region_alignment.jsonl}`; prediction E09; `src/docucheck/evaluation/metrics.py::evaluate_ocr_records`; `scripts/evaluate_ocr.py` | Tái tính trong bộ nhớ, toàn bộ summary và chi tiết per-image/per-region khớp. Tử/mẫu CER 92.591/49.449; WER 18.332/8.547. Tách whitespace, giữ dấu, micro trên vùng. Không phải KIE hoặc benchmark OCR độc lập. |
| E11 / Goal 2 | Hai lần hardening byte-identical; policies real-data lịch sử | `outputs/audit/goal2_hardening_20261028/{verification.json,verify_real_data.py,run_a/,run_b/,run_skip/}`; `outputs/audit/verification/reproducibility.json` | Gọi verifier trên run A/B thành công, so byte đủ bốn tệp. Không chạy lại preparation, skip hoặc fail trên dữ liệu thật; kết quả policy real-data là hồ sơ có sẵn. Hai JSONL gốc bằng byte với run A; split summary cùng JSON nhưng khác newline. `data/processed` thiếu checksum metadata nên verify-only từ chối dù manifest đạt cấu trúc. |
| E12 / báo cáo | Kiểm chứng tổng hợp và hình | report `verify_evidence.py`, `evidence/verified_summary.json`, `evidence/artifact_manifest.csv`, `figures/*.pdf` | Đã thực thi helper chỉ đọc input. CSV lưu bytes/SHA-256/Git tracking/distribution của nguồn và artifact. Hình tạo mới từ đặc trưng/metric thật, không thay thế artifact thí nghiệm gốc. |
| E13 / tests | 106 passed in 1.90s local | `tests/` (10 modules), đặc biệt `test_prepare_dataset_cli.py`, `test_annotation_validation.py`, `test_preprocessing.py`, `test_splitting.py`, `test_ocr_metrics.py`, `test_ocr_baseline.py`; report `evidence/pytest.txt`, `repository_context.json` | Thực thi Python 3.12.16/Windows, commit 4ee2776; synthetic fixtures, pytest cache tắt, basetemp dưới report QA. Không đồng nhất với 24/60/104 lịch sử hoặc CI. |
| E14 / notebook | Bốn notebook và visualization | `notebooks/01_dataset_audit.ipynb`, `02_exploratory_data_analysis.ipynb`, `03_preprocessing_validation.ipynb`, `04_ocr_baseline_evaluation.ipynb`; `src/docucheck/visualization/receipt.py` | Đã đọc code/output hiện có và kiểm cú pháp code cells. Lần lượt 7/7/4/3 code cells có execution count, không error output lưu sẵn. Chưa thực thi lại, execution count không chứng minh tái lập đầy đủ. |
| E15 / CI | Workflow và mức xác minh | `.github/workflows/tests.yml`; report `evidence/ci_status.json` | Đọc workflow Python 3.12/Ubuntu, dependency khóa, không cần raw data. GitHub connector trả `statuses: []`; chưa có log/check-run thành công được xác minh. |

## Các sai khác được giữ rõ trong PDF

- **OCR lịch sử:** 5.3.4; 29.849 boxes; CER 1,8965; WER 2,1795; 1.643 unmatched; 12.913 unassigned; 0,500 giây/ảnh. Chỉ có tài liệu mô tả, chưa có snapshot prediction riêng của lần chạy này.
- **OCR artifact hiện có:** 5.5.3.20260724; 26.859 boxes; CER 1,8725; WER 2,1448; 1.886 unmatched; 10.488 unassigned; runtime ghi 0,373664 giây/ảnh. Evaluation đã tái tính; runtime là metadata có sẵn. Không suy ra cải thiện giữa hai môi trường.
- **Model checksum:** dùng chuỗi đủ 64 ký tự khớp downloader, runtime và tệp local: `79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1`. Một chuỗi trong đoạn lịch sử của `WEEK1_REPORT.md` thiếu ký tự; không sao chép chuỗi đó như checksum hợp lệ.
- **Audit metadata:** summary lúc sinh mẫu vẫn `not_performed`; CSV review hiện tại ghi 40 reviewed. Sáu ảnh có phần bất định khác với hai kết luận tổng thể uncertain.
- **Bundle gốc:** structural validation đạt; verifier mới từ chối do thiếu checksums. Hai bundle hardening verify và bốn tệp bằng byte; không dùng checksum report lịch sử để gộp các thế hệ metadata.

## Manifest và quyền truy cập

`evidence/artifact_manifest.csv` ghi tên tương đối, kích thước, SHA-256 của đúng byte hiện có, cột `git_tracked` và phân phối. `git_tracked=true` có nghĩa được Git theo dõi trong workspace, không chứng minh byte local đã được push hoặc trùng commit. Bốn notebook có edits từ trước; cần cung cấp bản đúng hash nếu người chấm muốn tái kiểm cùng snapshot.

`private_local_do_not_publish` là artifact local cần gửi có kiểm soát nếu được phép. Không lấy tên ID hoặc hash làm bằng chứng ẩn danh hóa. Không đóng gói raw receipts, gallery HTML/overlay, model hoặc dữ liệu bí mật vào thư mục report.

## Bộ tệp cần đi cùng PDF

| Nhóm | Nội dung | Cách cung cấp |
|---|---|---|
| Báo cáo tự chứa để biên dịch | `main.pdf`, `main.tex`, hai `figures/*.pdf`, `BUILD.md`, `build.ps1` | Thư mục report |
| Minh chứng tổng hợp | `EVIDENCE_INDEX.md`, `SUBMISSION_CHECKLIST.md`, `verify_evidence.py`, `evidence/*` | Thư mục report; không chứa transcript |
| Implementation và notebook | README/docs/configs/src/scripts/tests/workflow, `pyproject.toml`, `uv.lock`, bốn notebook đúng hash | Repository ở commit đã ghi, kèm snapshot local notebook qua kênh được phép nếu cần; chưa tự đóng gói |
| Kết quả dữ liệu | Hai manifest + validation/split; hardening run A/B + verification JSON; review CSV/sample; near-duplicate candidate/summary/failures | Local Git-ignored; gửi riêng có kiểm soát, không publish mặc định |
| Kết quả OCR | Prediction/failures/runtime; metrics/per-image/per-region | Local Git-ignored; chứa transcript, gửi riêng có kiểm soát |
| Tái tính EDA từ ảnh | Dataset đúng byte, model nếu cần inference mới | Cấp quyền truy cập phù hợp điều khoản; không tự gửi raw dataset |

Không tự tạo ZIP chứa các artifact riêng tư. Bộ PDF hiện tại có thể đọc và biên dịch không cần raw dataset, nhưng kiểm tra độc lập sâu số liệu yêu cầu các nguồn riêng ở trên.

## Khoảng trống minh chứng

Chưa có snapshot OCR 5.3.4 lịch sử, log CI/check-run xanh, quyết định 36 cặp gần trùng, liên kết parent receipt/KIE cho recognition crops, hoặc taxonomy nguyên nhân OCR do con người gán nhãn. Không có bằng chứng field-level KIE vì mô hình/tác vụ đó chưa được đánh giá. Những phần này được ghi thiếu/chưa xác minh, không sinh dữ liệu thay thế.

Nguồn web chính thức đã đọc ngày 28/10/2026: [MC-OCR](https://www.rivf2021-mc-ocr.vietnlp.com/), [định dạng dataset](https://www.rivf2021-mc-ocr.vietnlp.com/dataset), [Tesseract CLI](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html), [revision tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast/tree/87416418657359cb625c412a48b6e1d6d41c29bd). Không dùng nguồn web để thay số liệu bản export local.

## Lượt rà soát và sửa bìa

`EDITORIAL_REVIEW.md` ghi kết quả đối chiếu ba goal và những phần đã cắt; `cover-preview.png` là ảnh render bìa mới. Bản tinh gọn giữ hai biểu đồ EDA/lỗi OCR và hai sơ đồ TikZ; bỏ biểu đồ KIE trùng số liệu với bảng. `evidence/goal_alignment_review.json` ghi lần kiểm tra mới: 79 hash không đổi, validation đạt 8.131 bản ghi, evaluation tái tính khớp toàn bộ artifact và 1.431 receipt của `skip` giữ nguyên nội dung/split. Không chạy lại OCR, preparation, notebook hoặc suite tests; kết quả `fail` trên dữ liệu thật vẫn là hồ sơ lịch sử, chỉ đối chiếu failure report và verification JSON.

## Kiểm tra nghiệm thu cuối

`evidence/final_review.json` ghi kết quả kiểm tra cuối về hash nguồn và bộ report, đồng bộ source/PDF, thông tin nhóm, placeholder, label/citation, figure assets, validation và các phép tính OCR. Phần PDF đã sẵn sàng trong phạm vi báo cáo Week 1; việc đính kèm notebook/artifact riêng tư theo yêu cầu nộp vẫn được theo dõi tách biệt trong checklist.
