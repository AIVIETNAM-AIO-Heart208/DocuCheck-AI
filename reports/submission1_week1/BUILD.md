# Biên dịch báo cáo tuần 1

Bản báo cáo dành cho người xem là main.pdf; nội dung LaTeX nằm trong main.tex. Hai hình tổng hợp được lưu trong figures/. Từ thư mục này, chạy XeLaTeX hai lần để cập nhật tham chiếu:

    xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex
    xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex

Tài liệu dùng font Times New Roman/Arial/Consolas nếu có font Windows; trên Linux dùng TeX Gyre Termes/Heros và DejaVu Sans Mono. Biên dịch PDF không cần dữ liệu gốc hay chạy lại OCR.

Bản dành cho người đọc được hoàn thiện ngày 29/10/2026, gồm 8 trang A4 (bìa và 7 trang nội dung, gồm tài liệu tham khảo). evidence/pdf_qa.json và evidence/final_review.json ghi kết quả kiểm tra bản hiện tại. EVIDENCE_INDEX.md là hồ sơ hỗ trợ riêng; các số liệu và ngữ cảnh lịch sử được ghi rõ trong đó, không chèn vào PDF.

Để biên dịch và kiểm tra bố cục bằng công cụ có sẵn trên Windows:

    powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -Render
    pdftotext -bbox-layout main.pdf qa/bbox.html
    ../../.venv/Scripts/python.exe quality_check.py

Script kiểm tra tạo ảnh tổng hợp trong qa/ và đánh dấu việc xem ảnh là đang chờ. Cần xem các trang render trước khi xác nhận bố cục; kiểm tra tự động không thay thế bước này.
