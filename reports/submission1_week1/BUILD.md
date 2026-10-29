# Biên dịch báo cáo tuần 1

Bản báo cáo dành cho người xem là main.pdf; nội dung LaTeX nằm trong main.tex. Hai hình tổng hợp được lưu trong figures/. Từ thư mục này, chạy XeLaTeX hai lần để cập nhật tham chiếu:

    xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex
    xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex

Tài liệu dùng font Times New Roman/Arial/Consolas nếu có font Windows; trên Linux dùng TeX Gyre Termes/Heros và DejaVu Sans Mono. Biên dịch PDF không cần dữ liệu gốc hay chạy lại OCR.

Bản dành cho người xem được biên tập ngày 29/10/2026, gồm 5 trang A4. evidence/pdf_qa.json ghi kết quả kiểm tra của bản hiện tại. Các hồ sơ kiểm chứng và rà soát cũ trong evidence/, EDITORIAL_REVIEW.md và EVIDENCE_INDEX.md là tài liệu kỹ thuật hỗ trợ, có thể mô tả phiên bản báo cáo 19 trang trước khi biên tập. Chúng không phải nội dung cần kèm vào PDF dành cho người xem.
