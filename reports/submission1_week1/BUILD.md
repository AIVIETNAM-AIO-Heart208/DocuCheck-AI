# Build và kiểm tra báo cáo

Source, hình tổng hợp và bibliography nội tuyến tự chứa trong thư mục này. Biên dịch không cần dataset, notebook, model, Python hoặc shell escape. Không có `references.bib` vì năm nguồn thực sự đã tham khảo được khai báo trực tiếp bằng `thebibliography` trong `main.tex`.

## Môi trường đã dùng

- Windows 11; MiKTeX-XeTeX 4.16 / MiKTeX 25.12, XeTeX 0.999997.
- Body 11 pt Times New Roman, headings Arial, code Consolas; load trực tiếp các font Windows có hỗ trợ tiếng Việt. Trên hệ khác, source dùng TeX Gyre Termes / Heros và DejaVu Sans Mono: cần cài đủ ba font trước build.
- Gói: `fontspec`, `geometry`, `graphicx`, `booktabs`, `tabularx`, `array`, `amsmath`, `float`, `needspace`, `xcolor`, `fancyhdr`, `caption`, `titlesec`, `enumitem`, `tikz` (arrows.meta, positioning), `url`, `hyperref`. Không cần `xurl`, BibTeX, Biber hoặc shell escape.
- PDF tools: `pdftoppm`, `pdftotext`, `pdfinfo` từ MiKTeX/Poppler.

## Biên dịch trên Windows / MiKTeX

Từ gốc repository:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File reports/submission1_week1/build.ps1 -Render
```

Script chạy ba pass, kiểm exit code và log cuối, từ chối missing glyph, undefined reference/citation, overfull box hoặc ignored error. `-disable-installer` tránh hộp thoại cài gói tự động. Nếu thiếu gói, cài các dependency đã liệt kê trong môi trường TeX trước khi chạy. `qa/` chứa log và ảnh kiểm tra, không bắt buộc đính kèm bản nộp.

Compiler cần quyền ghi vào cache/config/font cache người dùng của MiKTeX. Trong sandbox của lần lập báo cáo, build/render được chạy với quyền truy cập cấu hình MiKTeX thông thường đã được công cụ cho phép; không sửa source dự án hoặc cài thêm model/dependency Python. MiKTeX có thông báo chưa kiểm tra updates; đây là advisory của môi trường, không phải lỗi LaTeX hoặc thiếu glyph.

## Lệnh tương đương / hệ khác

Chuyển vào `reports/submission1_week1/` rồi chạy:

```text
xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex
xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex
xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex
pdfinfo main.pdf
pdftotext -layout main.pdf qa/extracted.txt
pdftoppm -r 110 -png main.pdf qa/page
```

Tạo `qa/` trước khi chạy lệnh render. TeX Live không cần flag riêng MiKTeX `-disable-installer`. Font khác hệ điều hành có thể làm đổi ngắt dòng/số trang; cần kiểm tra lại toàn bộ ảnh sau build. Reproducibility ở đây là cùng source/cấu hình tạo được nội dung và bố cục đã kiểm tra, không cam kết PDF byte-identical khi timestamp/font/engine thay đổi.

## Tái kiểm số liệu (tùy chọn, cần dữ liệu riêng tư)

Từ gốc repository, với môi trường Python 3.12 đã có dependency theo `uv.lock` và dataset/artifact đúng hash:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv/Scripts/python.exe reports/submission1_week1/verify_evidence.py
```

Helper chỉ đọc nguồn và ghi summary/hash/hai hình vào thư mục report. Nó không chạy OCR, preparation, notebook, pHash hoặc review pixel. Nó tái tính EDA từ ảnh thật và CER/WER từ prediction đã lưu; kiểm tra 8.131 image hashes/dimensions, CSV review, mẫu chọn, bundle A/B và metric/detail artifacts. Chạy lại sẽ cập nhật checksum/số liệu report theo input hiện có; kiểm PDF và nội dung nếu input thay đổi. Không chạy helper nếu chỉ muốn biên dịch.

Lệnh test đã thực thi trong lần lập báo cáo:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=reports/submission1_week1/qa/pytest-tmp
```

Kết quả gốc được giữ trong `evidence/pytest.txt`: 106 passed in 1.90s. `--basetemp` là thư mục scratch dành riêng; pytest có thể làm sạch nó khi chạy lại. Không đặt dữ liệu người dùng vào thư mục này.

## Biên tập và kiểm tra cuối

Đơn vị AI-VIETNAM, khóa học AIO2026 và nhóm Winner Winner Chicken Dinner (Nguyễn Văn Minh, Nguyễn Thành Trung) đã được xác nhận. Bìa bỏ mã học viên và giảng viên theo yêu cầu người dùng. Bìa ghi ngày lập báo cáo 28/10/2026; không suy ngày lập thành hạn nộp khi chưa có lịch chính thức. Khi sửa nội dung, build lại ba pass và kiểm tra các trang render. `evidence/pdf_qa.json` ghi QA của PDF được giao; không suy QA của PDF cũ áp dụng cho source đã sửa.

Bản tinh gọn đã biên dịch **19 trang A4**, gồm 13 trang nội dung chính, 1 bìa, 1 tóm tắt, 1 mục lục, 1 tài liệu tham khảo và 2 phụ lục. Log LaTeX cuối không còn warning về tham chiếu, font, overflow hoặc bảng; toàn bộ trang đã render và kiểm tra trực quan.

Để lặp lại phần kiểm tra tự động sau build, chạy `pdftotext -bbox-layout main.pdf qa/bbox.html` trong thư mục báo cáo, rồi từ gốc repository chạy `.venv/Scripts/python.exe reports/submission1_week1/quality_check.py`. Helper QA kiểm log, nội dung chính, các word bounds trong trang và hash của 79 source/artifact được đối chiếu; tạo contact sheets dưới `qa/`. Nó đặt trạng thái visual review về pending vì cần xem lại các PNG sau mỗi bản build. `quality_check.py` không thay thế kiểm tra trực quan.

`evidence/submission_manifest.csv` ghi hash các tệp thực sự thuộc bộ report bàn giao, trừ chính manifest và scratch QA. Nếu sửa nội dung, cần build/QA lại và cập nhật manifest; timestamp của PDF có thể thay đổi hash dù nội dung giữ nguyên.

Bản sửa bìa có ảnh xem trước `cover-preview.png`; tạo lại bằng `pdftoppm -f 1 -l 1 -singlefile -r 130 -png main.pdf cover-preview` trong thư mục report. `EDITORIAL_REVIEW.md` ghi các vấn đề đã chỉnh và những khoảng trống minh chứng còn lại sau rà soát.
