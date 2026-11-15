# Web demo DocuCheck AI

## Tổng quan

Web tích hợp API, hàng đợi, worker OCR–Qwen và giao diện xem/sửa/xác nhận kết
quả. Nhóm đã demo luồng xử lý và phát hành image Docker chứa model tại
`heart2082006/docucheck-ai`. Cấu hình mặc định là refined/exclusive.

CLI mặc định baseline; web mặc định `EXTRACTION_MODE=refined`. OCR dùng
PHOCR–VietOCR CUDA, E1 scale 2 Lanczos, padding 10% có guard/fallback và
gợi ý merged_predictions. Độ chính xác phụ thuộc chất lượng ảnh và bố cục.

## Luồng sử dụng

1. Mở `http://localhost:8000`, chờ dịch vụ kiểm tra model bundle/GPU.
2. Chọn JPEG/PNG/WebP, tối đa 15 MiB và 25 MP, một biên lai một trang.
3. Nhấn Trích xuất: hàng đợi → nạp model → OCR → Qwen → kết quả.
4. Nhấn tên field để tô polygon bằng chứng AI trên ảnh chuẩn hóa. Đây là vùng
   OCR gốc, không phải bbox ký tự suy đoán. Bản sửa không thay bằng chứng AI gốc.
5. Kiểm tra các thông tin “Cần kiểm tra”, sửa nếu cần, nhấn Lưu bản sửa rồi Xác
   nhận. Sửa sau xác nhận phải lưu/xác nhận lại. AI và các revision được giữ riêng.
6. Tải JSON từ AI hoặc JSON đã xác nhận, đúng bốn field. Ngày/giờ trong file là
   ISO, giữ độ chính xác nguồn; tổng tiền là integer/null. UI không tự gán ngoại tệ.

Một phiên có tối đa hai tác vụ chưa kết thúc, hàng chờ bốn tác vụ, một GPU job.
Ảnh lưu tạm khoảng 24 giờ; các job terminal quá TTL được dọn khi coordinator
hoạt động. Thay đổi giới hạn qua `.env`. Đổi ảnh gỡ result cũ; double click/retry
dùng idempotency key. Khi trang reload, job cuối của tab được nối lại bằng session.

## Kiến trúc và lifecycle

`api.py` phục vụ giao diện tĩnh cùng origin, `storage.py` lưu SQLite/job/review,
`coordinator.py` sở hữu hàng đợi và điều phối qua thread, `engine.py` quản lý
process OCR/extraction và llama-server, `inference_worker.py` tái sử dụng models.
API không import Torch/ONNX/model; upload decode chạy trong thread riêng.

- Uvicorn **một worker, không reload**. Storage có khóa instance, tránh vô tình
  chạy nhiều worker cùng thư mục. Không chạy CLI GPU song song với web.
- `GPU_POLICY=exclusive` mặc định: đóng Qwen trước OCR, đóng OCR và chờ giải phóng
  GPU trước Qwen. API/extraction worker CPU vẫn sống. Có thể phải nạp lại model
  mỗi ảnh; đây là trade-off để tránh giả định hai engine cùng vừa 8 GB.
- `GPU_POLICY=resident`: giữ OCR + llama-server cho các job kế tiếp. Chỉ bật khi
  **bạn đã kiểm chứng VRAM tổng trên máy đích**; cần `RESIDENT_VALIDATED=true`.
  `RESIDENT_FREE_MIB=7000` là ngưỡng free trước khi nạp hai engine lần đầu,
  không phải bằng chứng chúng chắc chắn vừa VRAM. GPU 8 GB có headroom thay đổi
  theo ứng dụng khác, KV cache và số box OCR. Preflight không thể dự đoán mọi OOM.
- Timeout OCR/extraction/startup 180 s, total inference 600 s mặc định. Mỗi stage
  thông qua JSON-line IPC có deadline; cancel dừng worker/process group trước
  khi job tiếp theo được claim. Không retry OOM, đổi engine hoặc chạy CPU âm thầm.
- Lỗi worker/timeout/cancel đóng các tiến trình sở hữu. Qwen được khởi tạo lại ở
  job sau nếu cần; worker/server resident chỉ nạp một lần khi không lỗi.
- Shutdown set cancellation rồi đợi thread dọn process; Docker có init và grace
  period. Queue chưa chạy không tự replay sau restart; bị đánh dấu interrupted.
- `/health/live` không nạp model/hash weights. `/health/ready` cho biết đã kiểm
  tra bundle và GPU để nhận job, **không khẳng định actual model đã được nạp**.
  OCR provider và Qwen full offload được kiểm tra lúc engine nạp trong job đầu.
  Busy vẫn ready, tránh restart chỉ vì đang inference. Config/GPU chưa sẵn sàng
  thì status 503. Resident check thất bại không tự chuyển exclusive.

## Chạy local Windows, tận dụng môi trường OCR đang có

Không sync toàn bộ extras vào môi trường OCR: PHOCR dùng NumPy <2, core NumPy >=2.
Tạo môi trường web riêng (nhẹ, không cài Torch/PHOCR):

```powershell
Set-Location C:\Python\AIO\DocuCheck-AI
.\.venv\Scripts\python.exe -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install -r requirements/web.lock
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Trên máy repo hiện tại, Python 3.12 được uv quản lý và `.venv/pyvenv.cfg` trỏ
về runtime đó. Python Launcher `py -3.12` có thể không tìm thấy runtime uv, nên
lệnh trên dùng interpreter repo đã có. Nếu setup trên máy mới chưa có `.venv`,
cần chuẩn bị Python 3.12 trước, hoặc dùng `uv venv --python 3.12 --seed .venv-web`.

Bundle weights từ files đã có trong `outputs/`; lệnh sau chỉ tải YAML VietOCR,
không tải lại model hoặc chạy inference. `models/` phải chưa tồn tại. Nếu đã có
bundle, giữ lại hoặc chọn `--destination` khác rồi đổi MODEL_DIR.

```powershell
.\.venv-web\Scripts\python.exe scripts/prepare_web_models.py --source-root outputs --destination models --fetch-config
```

Không muốn truy cập mạng: truyền `--config-file path/to/merged_vietocr.yml` thay
`--fetch-config`. YAML cần là base + vgg_transformer config hoàn chỉnh như phiên
bản CLI dùng. Script kiểm tra kiến trúc, pin/hash Qwen và PHOCR, ghi hash thực
VietOCR/config; hash local không tự chứng minh license hoặc nguồn tải đáng tin.

Trong `.env` thêm/sửa đường dẫn Windows của bạn, không copy các đường `/models`
của container vào lệnh local:

```dotenv
MODEL_DIR=C:/Python/AIO/DocuCheck-AI/models
STORAGE_DIR=C:/Python/AIO/DocuCheck-AI/outputs/web
OCR_PYTHON=C:/Python/AIO/DocuCheck-AI/.venv-phocr-gpu/Scripts/python.exe
LLAMA_BINARY=C:/Python/AIO/DocuCheck-AI/outputs/runtime/llama-b12345/llama-server.exe
EXTRACTION_MODE=refined
GPU_POLICY=exclusive
RESIDENT_VALIDATED=false
```

`LLAMA_BINARY` phải trỏ đúng file hiện có (nếu giải nén vào thư mục con, chỉnh lại).
Đường model startup không phụ thuộc MC-OCR/dataset. Không chạy .venv-web bằng
`uv run` từ core project vì có thể sync dependency ngoài ý muốn.

```powershell
.\.venv-web\Scripts\python.exe scripts/serve_web.py
```

Mở `http://localhost:8000`, dừng bằng Ctrl+C. Bind mặc định localhost; chưa có
đăng nhập đầy đủ nên chỉ dùng local demo. Muốn đưa ra Internet cần thiết kế
auth, HTTPS/rate limits; đây không nằm trong phạm vi hiện tại.

Chuyển resident sau khi tự kiểm chứng:

```dotenv
GPU_POLICY=resident
RESIDENT_VALIDATED=true
RESIDENT_FREE_MIB=7000
```

Restart web sau thay đổi env. Không khẳng định resident nhanh/vừa 8 GB cho đến
khi chạy đo. Không dùng thông số model load trên CLI cũ làm số latency web mới.

## Docker GPU

Chi tiết nộp: [DOCKER_SUBMISSION.md](DOCKER_SUBMISSION.md).

Điều kiện: NVIDIA GPU, driver tương thích CUDA 12.8; Docker Compose v2 hỗ trợ
GPU reservation. Windows dùng Docker Desktop Linux containers + WSL2, driver
host hỗ trợ WSL GPU. Linux cần NVIDIA Container Toolkit. Không cần cài driver
vào image. Bản mặc định build llama CUDA architecture 89 cho RTX 4060; muốn
dùng GPU khác cần build với architecture phù hợp, không coi image này universal.

Sau khi chuẩn bị `models/` và `.env`:

```powershell
docker compose build --build-arg BUILD_REVISION=$(git rev-parse HEAD)
docker compose up -d --no-build
docker compose logs -f web
```

Hoặc `docker compose up --build` để build/start một lần. Mở localhost:8000.
Compose mount model read-only `/models`, storage named volume `/var/lib/docucheck`,
chỉ expose web, limit RAM 10 GB/CPU 4. Đây là budget khởi điểm chưa benchmark;
RAM/CPU limit **không** giới hạn VRAM. Không gọi `down -v` khi sửa lỗi.

```powershell
docker compose down
```

Docker Linux dùng `requirements/web.lock` và `inference.lock`, NumPy 1.26.4,
Torch 2.11.0/torchvision 0.26.0 cu128, ORT GPU 1.26.0, PHOCR 1.0.3, VietOCR
0.3.13; đối chiếu với các distribution đang cài local và tài liệu CUDA, **chưa
build/resolve/chạy kiểm chứng trên Linux**. File lock là danh sách version pin
runtime, không phải solver lock có hashes cho mọi wheel. Wheel CUDA phụ thuộc
theo metadata bản Torch pin; nên lưu image archive/digest đã build cho gói offline.

PHOCR/VietOCR được cài `--no-deps` với tập runtime import cần dùng; không gồm
training/dataset extras. `pip check` có thể báo training deps thiếu; không dùng
image này để train. Dependency import closure và thư viện CUDA thực phải được
smoke-test trước nộp. Không thay constraint core trong pyproject/uv.lock.

## API

| Endpoint | Chức năng |
|---|---|
| GET `/api/session` | Cookie phiên HttpOnly, giới hạn upload/retention |
| POST `/api/jobs` | Multipart `file`, header `Idempotency-Key`, trả 202 + job ID |
| GET `/api/jobs/{id}` | State, field issues, review, timing, queue position |
| POST `/api/jobs/{id}/cancel` | Hủy queued hoặc yêu cầu dừng job chạy |
| PUT `/api/jobs/{id}/review` | `{values:{4 fields}, revision:0, confirmed:false}` |
| GET `/api/jobs/{id}/download?version=ai` | JSON AI bốn field |
| GET `/api/jobs/{id}/download?version=reviewed` | JSON bản đã xác nhận |
| GET `/api/jobs/{id}/image` | PNG đã chuẩn hóa để overlay |
| GET `/health/live`, `/health/ready` | Liveness và khả năng nhận job |

Session cookie là bearer capability của demo; người biết job ID mà không có
cookie không truy cập được job. Mất cookie không khôi phục qua UI hiện tại.
SQLite không lưu cookie gốc; lưu hash owner. API không trả path host/traceback.
Origin check + SameSite strict, JS dùng textContent, model internal bind loopback.

Upload được spool có giới hạn body trước parse và file-size khi copy; ảnh decode
một lần, EXIF transpose/RGB, không resize/cắt. Evidence dùng pixel space của PNG
này. `normalize_upload` giữ hash/kích thước/orientation gốc, không giữ file upload
gốc sau chuẩn hóa. MIME khai báo không thay thế việc decode format thật.

## Dữ liệu, diagnostics và lỗi

Trong storage root: `jobs.sqlite3` (metadata/review revisions), UUID job directories
(`image.png`, `ocr/`, `inputs/`, `requests/`, `responses/`, `extraction.json`,
`receipt.ai.json`, `runtime.json`). Raw OCR/request/response chỉ local, không gửi
toàn bộ ra UI. Log engine giữ một file hiện tại + previous khi quay vòng lúc nạp.
Docker stdout log có rotation riêng. Chỉ dọn job terminal theo TTL; không xóa model.

`succeeded` = pipeline hợp lệ với field status ok; vẫn có thể sai về nội dung.
`partial` = có dữ liệu nhưng thiếu/needs_review/partial OCR. Null vẫn null; UI
review là quyết định người dùng, không phải kết luận AI chính xác 100%.

| Lỗi | Cách kiểm tra |
|---|---|
| Ready 503 | Model path/manifest/hash, llama binary, `nvidia-smi`, engine startup log |
| OCR worker fail | `.venv-phocr-gpu`, YAML offline, Torch/ORT CUDA/cuDNN, log OCR |
| Qwen fail/startup | Port 8097 bận, binary Linux/Windows đúng hệ, weights, log full offload |
| GPU OOM | Dừng CLI/job ngoài, dùng exclusive; không ép CPU hoặc tăng retry |
| Context exceeded | Bill quá dài; giữ lỗi thật, không cắt nội dung hoặc tự fallback |
| Hàng đợi 429 | Chờ hoặc hủy tác vụ phiên mình rồi gửi lại |
| Job interrupted | App restart; gửi job mới, không dùng artifact cũ làm kết quả |
| Link JSON reviewed 409 | Lưu rồi xác nhận revision mới nhất |

llama-server dùng `-lv 4` để ghi thông tin offload; bộ điều phối kiểm tra đủ
layer GPU trước khi xử lý. Job lỗi lưu `failure.json` tại thư mục UUID;
API chỉ trả code/thông báo đã lọc, không trả traceback hoặc đường dẫn host.

Worker Python dùng `-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` và
reconfigure stdio để truyền văn bản tiếng Việt nhất quán trên Windows/Linux.
IPC dùng JSON ASCII-escaped ở cả hai chiều; sau json.loads văn bản Unicode giữ
nguyên, artifacts vẫn UTF-8. Không dùng errors=ignore/replace cho dữ liệu biên lai.
Lỗi decode từ pipe được phân biệt với lỗi nội bộ worker.

Không hủy process ngoài app; cancel không kết thúc kernel GPU tức thì mọi trường
hợp, phải đợi terminate/kill và worker unwind. Nếu cleanup thất bại, cần dừng app
và kiểm tra process trước khi gửi tiếp.

## Quy trình kiểm tra khi phát triển và phát hành

```powershell
# Chạy test web trong môi trường có FastAPI/httpx + pytest
.\.venv-web\Scripts\python.exe -m pip install pytest==8.4.2
$env:PYTHONPATH = "$PWD/src"
.\.venv-web\Scripts\python.exe -m pytest tests/test_web_storage.py tests/test_web_api.py tests/test_web_engine_lifecycle.py tests/test_web_offline_config.py tests/test_web_ipc.py
```

Sau đó chạy bộ regression core trong môi trường core hiện có; web test API sẽ
skip nếu thiếu optional dependencies. Tests fake không xác minh CUDA/offline,
UI thực, Docker, process-tree cleanup OS hoặc quality extraction.

Checklist manual: upload đúng/sai; ảnh EXIF; đổi ảnh không stale; click evidence;
null/0/ngày thiếu giờ; save/confirm/revision từ hai tab; cancel; hai request đồng
thời; quá queue; model thiếu; OCR fail; timeout; Ctrl+C/restart; Docker; tắt mạng.
Đối chiếu CLI/web trên cùng ảnh/OCR, cùng config; normalized input có EXIF thay
đổi cần ghi nhận khi so sánh kết quả CLI và web.

Đo opt-in sau khi tự khởi động web, chọn tối thiểu hai ảnh, chạy sáu job tuần tự:

```powershell
.\.venv-web\Scripts\python.exe scripts/benchmark_web.py "C:/bills/a.jpg" "C:/bills/b.jpg" --allow-inference --jobs 6 --output outputs/web_benchmark_exclusive.json
```

Đổi policy/restart rồi chạy output khác cho resident. Job đầu chỉ là cold nếu
server chưa nhận job trước; năm job sau không mặc nhiên warm-model ở exclusive.
Harness ghi mỗi lượt và lỗi, không chấm accuracy. Runtime từng job ghi load count,
queue/OCR/Qwen/load/total, token usage, RAM process-tree/GPU toàn máy sampling
theo stage (không phải peak chính xác). Kết quả đo gắn với cấu hình và phần cứng
của từng lượt chạy.

## Phạm vi và giới hạn

- Model bundle lưu checksum để đối chiếu tính toàn vẹn; license/model cards
  đi kèm nguồn phân phối trọng số.
- Đây là demo một node, một GPU, một worker. Chưa có auth production, multi-node,
  PDF/đa trang hoặc cache kết quả. Các lỗi lựa chọn tên/địa chỉ của model vẫn tồn tại.
- EXIF normalization và đường runtime Linux là thay đổi integration có thể làm
  output khác CLI cũ; so sánh trên cùng ảnh đã chuẩn hóa và cùng cấu hình.
- Threshold/budget/TTL là cấu hình có thể điều chỉnh theo tài nguyên và dữ liệu.

Nguồn kỹ thuật: [Docker GPU Windows](https://docs.docker.com/desktop/features/gpu/),
[Compose GPU](https://docs.docker.com/compose/how-tos/gpu-support/),
[ORT CUDA](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html),
[PyTorch versions](https://pytorch.org/get-started/previous-versions/),
[llama b12345](https://github.com/ggml-org/llama.cpp/tree/b12345).
## Trạng thái giao diện và kiểm tra kết quả

UI khóa nhập và chặn gửi lặp khi đang lưu/xác nhận. Đổi ảnh bỏ qua phản hồi cũ;
tải JSON dùng no-store và bỏ download không còn khớp ảnh/bản sửa. CI có job web
riêng cùng test form bằng Node fake DOM. Mặc định refined/exclusive.

Checklist bảo trì: lưu khi mạng chậm, bấm lặp, đổi ảnh lúc đang lưu,
xác nhận/tải hai phiên bản JSON; kiểm tra tên/địa chỉ trên ảnh. Model có thể chọn
sai dù JSON hợp lệ. Xem [báo cáo kỹ thuật](../reports/DocuCheck_AI_Technical_Report.pdf)
để biết phương pháp và phạm vi kết quả.

