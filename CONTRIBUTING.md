# Phát triển và bảo trì

## Môi trường

Python 3.12. Đọc docs/WEB_DEMO.md cho web/GPU; requirements/web.lock và
requirements/inference.lock phục vụ môi trường tách biệt với core uv.lock.
Không dùng uv sync --all-extras cho môi trường web đang chạy ổn.

## Ranh giới module

- `extraction/contracts.py`: bốn field và mode được hỗ trợ, không import model.
- `extraction/artifacts.py`: ghi diagnostic JSON UTF-8; API public giữ bốn field.
- `extraction/qwen.py`: adapter/client; tiếp tục re-export FIELDS/write_json để
  các CLI và consumer cũ không hỏng import sau refactor.
- `web/`: API, trạng thái job/review, UI và lifecycle subprocess. Không đưa
  logic chọn field hoặc thư viện OCR nặng vào API process.
- `ocr/`, `data/`, `evaluation/`: OCR và nghiên cứu dùng chung. Tesseract chỉ là
  baseline lịch sử; không xóa các adapter/protocol vẫn được test tham chiếu.

Giữ mặc định CLI baseline, web refined/exclusive. Muốn đổi semantic selection,
preprocessing hoặc model cần task và đánh giá riêng. Refactor phải giữ prompt,
ID, exact spans, ordering và public JSON; không dùng nhãn dataset ở runtime.

## Kiểm tra do người phát triển chủ động thực hiện

Core:

```bash
uv sync --locked --extra dev
uv run python -m pytest
```

Web trong môi trường đã có requirements/web.lock và pytest:

```powershell
.\.venv-web\Scripts\python.exe -m pytest tests/test_web_api.py tests/test_web_storage.py tests/test_web_engine_lifecycle.py tests/test_web_ipc.py tests/test_web_offline_config.py
node --test tests/web_review_state.test.cjs
```

CI có job web riêng. Fake tests không thay cho browser/GPU/receipt thật.
Không ghi test đã pass nếu chưa chạy. Quyền chạy test/OCR/model trong phiên
làm việc với trợ lý tuân theo yêu cầu của người dùng.

## File sinh ra và bàn giao

Không commit .env, dataset, model, output upload/review, virtualenv, cache hay
archive ZIP/TAR. Trước commit xem `git diff --stat`, `git diff --cached --stat`
và `git status --short`. ZIP/TAR gửi qua Drive/USB, không GitHub.

`submission/source.zip`, image, tar và ZIP ngoài repo là snapshot đã đóng gói;
chỉnh source không cập nhật chúng. Chỉ build/export gói mới theo hướng dẫn
docs/DOCKER_SUBMISSION.md sau khi kiểm chứng. Không sửa commit/push tự động.
