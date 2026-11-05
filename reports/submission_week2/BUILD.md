# Biên dịch báo cáo Week 2

Ngày lập báo cáo: 06/11/2026, Asia/Saigon. Bản đã kiểm tra có **11 trang A4**, gồm trang tài liệu tham khảo có liên kết tới năm nguồn chính thức. Đầu ra chính: `main.pdf`; nguồn: `main.tex` và hai hình vector trong `figures/`.

Dùng XeLaTeX, kế thừa Times New Roman/Arial/Consolas trên Windows từ Week 1. Linux dùng TeX Gyre Termes/Heros và DejaVu Sans Mono. Không cần dữ liệu hoặc model OCR để biên dịch từ những hình đã có.

Từ thư mục báo cáo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -Render
```

Hoặc chạy hai lần (thêm lần thứ ba nếu tham chiếu còn thay đổi):

```text
xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape -disable-installer main.tex
```

`build.ps1` chạy ba lượt, kiểm tra log và render PNG bằng Poppler. Các log, ảnh trang, text trích xuất và thông tin PDF nằm trong `qa/`. Phải xem ảnh trang sau khi thay đổi nội dung; kiểm tra log không thay thế review trực quan.

Từ gốc repo, chỉ khi cần tạo lại hình và kiểm tra số liệu đọc từ artifact:

```powershell
.\.venv\Scripts\python.exe -X utf8 reports/submission_week2/prepare_report.py
```

Script dùng matplotlib và đọc bundle local. Không chạy inference, evaluator, notebook, pytest hoặc sửa benchmark. Nó kiểm tra SHA-256 theo inventory, cộng các lỗi đã lưu và xuất hai biểu đồ. `evidence/protected_before.json` là mốc hash được tạo lần đầu và không bị ghi đè khi chạy lại.

Hình biểu diễn số đo thật, không tái phân phối ảnh hóa đơn hoặc transcript gốc. Tên cơ sở đào tạo, khóa học, nhóm và hai thành viên lấy từ Week 1. Không ghi số submission hoặc Module 05 trên bìa Week 2 vì chưa có nguồn xác nhận riêng cho đợt nộp này.
