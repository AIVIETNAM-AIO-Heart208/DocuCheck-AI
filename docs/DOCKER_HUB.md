# DocuCheck AI

Trích xuất tên người bán, địa chỉ, ngày/giờ giao dịch và tổng tiền từ ảnh biên
lai. Có giao diện kiểm tra, chỉnh sửa, xác nhận và tải JSON.

Image chứa sẵn PHOCR, VietOCR và Qwen3-4B Q4_K_M. Không cần cài Python,
tải model, nhận ZIP hoặc clone source. Hướng dẫn này áp dụng sau khi publisher
đã build target bundled và push thành công image heart2082006/docucheck-ai.

## Chạy lần đầu

Yêu cầu máy có NVIDIA GPU, driver tương thích và Docker hỗ trợ GPU. Windows
dùng Docker Desktop với Linux containers và WSL2. Bản build nhắm RTX 4060 8 GB;
chưa xác minh mọi loại GPU. Cổng 8000 phải còn trống.

Mở Docker Desktop, sau đó mở PowerShell/terminal và chạy:

```powershell
docker run -d --name docucheck-ai --gpus all -p 127.0.0.1:8000:8000 heart2082006/docucheck-ai
```

Lần đầu Docker tự tải image nếu máy chưa có; image lớn vì chứa runtime GPU và
model. Khi lệnh xong, mở **http://localhost:8000**, đợi dịch vụ sẵn sàng rồi tải
ảnh biên lai. Mặc định refined/exclusive. Kết quả AI cần được kiểm tra trên ảnh.

## Những lần sau

```powershell
docker start docucheck-ai
```

Dừng bằng `docker stop docucheck-ai`. Có thể Start/Stop container cùng tên trong
Docker Desktop. Không chạy lại lệnh tạo container lần đầu nếu container đó còn
tồn tại. Lệnh đơn giản trên giữ dữ liệu trong container khi Stop/Start; xóa
container sẽ làm mất ảnh/bản sửa lưu trong nó.

Nếu web không sẵn sàng, lấy log bằng:

```powershell
docker logs --tail 100 docucheck-ai
```

GPU không tương thích, thiếu VRAM, cổng bị chiếm hoặc Docker chưa được cấp GPU
cần được xử lý trên máy nhận. Không có CPU fallback tự động. Lượt đầu xử lý
ảnh cần nạp model; thời gian thay đổi theo máy và ảnh.

## Cho người phát hành

Copy nội dung file này vào **Docker Hub → heart2082006/docucheck-ai → Overview →
Edit** để người nhận đọc được ngay trên trang image. Docker push chỉ đẩy image,
không tự đăng nội dung README lên Overview. File này cũng được kèm trong image
tại `/app/DOCKER_HUB.md` sau lần build tiếp theo.

Build/push theo docs/DOCKER_SUBMISSION.md. Cấu hình bundled được chuẩn bị nhưng
chưa được trợ lý build/push hoặc kiểm chứng inference trong lượt thay đổi này.
