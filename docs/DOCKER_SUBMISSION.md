# Đóng gói nộp web demo GPU

## Docker Hub: image chứa sẵn model

Target **bundled** chứa ứng dụng, CUDA runtime và toàn bộ weights/config của
PHOCR, VietOCR và Qwen tại /models. Người nhận không cần ZIP, tar hay model riêng.

Publisher tạo repository Public `docucheck-ai` trên Docker Hub, rồi chạy tại gốc repo:

```powershell
docker login
docker build --target bundled --build-context model_bundle=./models -t heart2082006/docucheck-ai .
docker push heart2082006/docucheck-ai
```

Giữ cả `--target bundled` và `--build-context`. Build thường vẫn tạo runtime
không chứa weights để tương thích Compose local cũ. Named context của BuildKit
đưa model vào image mà không bỏ quy tắc ignore model/dataset trong source context.
Chỉ file weights, config, manifest và notice được liệt kê được copy.

Người nhận có NVIDIA GPU/driver và Docker hỗ trợ GPU, chạy:

```powershell
docker pull heart2082006/docucheck-ai
docker run -d --name docucheck-ai --init --gpus all --cpus 4 --memory 10g -p 127.0.0.1:8000:8000 -v docucheck-data:/var/lib/docucheck -e EXTRACTION_MODE=refined -e GPU_POLICY=exclusive heart2082006/docucheck-ai
```

Mở http://localhost:8000. Không mount vào /models vì model đã có trong image.
Windows dùng Docker Desktop Linux containers/WSL2. Repository private cần
đăng nhập bằng tài khoản có quyền pull. Không ghi tag thì Docker dùng latest.

Log: `docker logs -f docucheck-ai`. Dừng: `docker stop docucheck-ai`.
Khởi động lại container đã có: `docker start docucheck-ai`.

Image bundled được phát hành tại `heart2082006/docucheck-ai`.
Runtime kiểm tra checksum bundle lúc startup. Model notice được
đưa vào image; bảo đảm quyền phân phối weights khi xuất bản public.

## Phân phối bằng image tar

Luồng tar là phương án bàn giao offline, gồm docucheck-ai.tar, model bundle,
checksum và source.zip trong submission/. Docker Hub là phương án bàn giao
chính. Thông tin phiên bản của gói offline nằm trong BUILD_STATUS.md kèm gói.

## Phạm vi môi trường

- NVIDIA GPU; bản build mặc định architecture 89 (RTX 4060), CUDA 12.8 Linux
  x86_64. Driver host phải tương thích. Windows dùng Docker Desktop WSL2 Linux
  containers, Linux dùng NVIDIA Container Toolkit.
- Luồng demo yêu cầu NVIDIA GPU, không có CPU fallback tự động.
- Cấu hình khởi điểm: RAM container 10 GB, 4 CPU. Exclusive là policy mặc định;
  resident cần ngân sách VRAM phù hợp. Build CUDA cần thêm RAM/disk/cache tạm.

## Gói source và setup online

Nộp source có `src/`, `configs/`, `scripts/`, `requirements/`, `Dockerfile`,
`compose.yaml`, `.dockerignore`, `.env.example`, tài liệu này và WEB_DEMO.md.
Không nộp `.venv*`, `.git`, ảnh dataset/upload/review thật, secrets hoặc output
thử nghiệm. Trước nộp, commit code/test/docs sau kiểm chứng để xác định revision.

Chuẩn bị bundle bằng `scripts/prepare_web_models.py` theo WEB_DEMO.md. Script
dùng weights local hiện có, không tự tải weights thiếu. Nếu máy sạch chưa có
weights, dùng nguồn/hash trong config repo và scripts tải OCR/Qwen đã có, hoặc
nhận bundle checksum từ nhóm. Script tải Qwen cũ đồng thời tải runtime Windows;
Docker không cần runtime đó. Linux binary được build bởi Dockerfile.

Nội dung bundle phải có:

```text
models/
  manifest.json
  SOURCES_AND_LICENSES.md
  qwen/model.gguf
  phocr/ch_PP-OCRv5_server_det.onnx
  vietocr/vgg_transformer.pth
  vietocr/config.yml
```

Manifest ghi SHA256 thực. Qwen/PHOCR được đối chiếu hash pin; VietOCR/config
được ghi hash snapshot local để đối chiếu tính toàn vẹn.
Bổ sung license text/model card/notice cần thiết từ nguồn phân phối; link nguồn
trong notice không tự thay thế license grant. Docker có bản LICENSE llama.cpp.

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
docker compose build --build-arg BUILD_REVISION=$(git rev-parse HEAD)
docker compose up -d --no-build
```

Mở localhost:8000, kiểm tra ready và upload ảnh thật. Build chỉ cần mạng tải base
images/wheels/source; inference sau setup không cần mạng tải config/model. Kiểm
tra chế độ offline khi chuẩn bị bản phát hành không cần kết nối mạng.

## Gói offline

Chỉ thực hiện sau khi build và smoke-test thành công. Tạo thư mục submission
mới; các lệnh dưới giả định `models/` là bundle đã chuẩn bị. Cần đủ disk cho bản
copy weights và image archive. Không copy volume chứa ảnh/review cá nhân.

```powershell
New-Item -ItemType Directory -Path submission
docker save --output submission/docucheck-ai.tar docucheck-ai:demo-v1
Copy-Item -LiteralPath compose.yaml -Destination submission/compose.yaml
Copy-Item -LiteralPath .env.example -Destination submission/.env.example
Copy-Item -LiteralPath models -Destination submission/models -Recurse
Copy-Item -LiteralPath docs/WEB_DEMO.md -Destination submission/WEB_DEMO.md
Copy-Item -LiteralPath docs/DOCKER_SUBMISSION.md -Destination submission/README.md
Copy-Item -LiteralPath docs/DOCKER_SUBMISSION.md -Destination submission/DOCKER_SUBMISSION.md
Get-FileHash -Algorithm SHA256 submission/docucheck-ai.tar | Format-List | Out-File -Encoding utf8 submission/image-checksum.txt
docker image inspect docucheck-ai:demo-v1 --format '{{.Id}}' | Out-File -Encoding utf8 submission/image-id.txt
```

Thêm revision source, host/driver/GPU, lệnh build và kết quả smoke-test thực vào
phiếu bàn giao. Model checksums nằm
trong manifest. `docker save` **không** đưa model bind mount/volume vào image tar;
phải nộp cả `models/`. Yêu cầu license/model cards vẫn áp dụng cho bundle offline.

Máy chấm có Docker/driver GPU sẵn, từ thư mục submission:

```powershell
docker load --input docucheck-ai.tar
Copy-Item -LiteralPath .env.example -Destination .env
docker compose up -d --no-build --pull never
docker compose logs -f web
```

Source/Dockerfile không cần có mặt khi `--no-build` và image đã load đúng tag;
Compose vẫn chứa build stanza nhưng không thực thi. Không đổi tag trong image
inspect/compose giữa lúc export và nộp. Dùng image archive đã build tránh resolver
wheels/base tag đổi khi máy chấm không có mạng.

## Dữ liệu và dừng

Model read-only `/models`. Job/upload/reviews ở volume `web-data`; app tự tạo
thư mục writable theo UID 10001. Named volume mới nhận ownership từ image;
nếu dùng bind mount dữ liệu thay thế phải cấp quyền cho UID này.

```powershell
docker compose down
```

Lệnh này giữ dữ liệu/weights. Không dùng `down -v` trừ khi chủ động muốn xóa
toàn bộ dữ liệu demo. Dừng sạch/khởi động lại, upload lỗi, hủy job, quá hàng đợi,
hai tab, offline, hash/model thiếu nằm trong checklist bảo trì bản phát hành
ở WEB_DEMO.md.
