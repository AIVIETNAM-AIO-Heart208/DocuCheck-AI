# syntax=docker/dockerfile:1
# Linux CUDA runtime; select the bundled target to include model weights.
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04 AS llama-build
ARG LLAMA_REF=b12345
ARG CUDA_ARCHITECTURES=89
RUN apt-get update && apt-get install -y --no-install-recommends git cmake ninja-build g++ ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${LLAMA_REF} https://github.com/ggml-org/llama.cpp.git /llama
RUN cmake -S /llama -B /llama/build -G Ninja -DGGML_CUDA=ON -DGGML_NATIVE=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DBUILD_SHARED_LIBS=OFF -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES} -DCMAKE_BUILD_TYPE=Release && cmake --build /llama/build --target llama-server --parallel 4

FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04 AS app
ARG BUILD_REVISION=unknown
LABEL org.opencontainers.image.title="DocuCheck AI" org.opencontainers.image.revision=${BUILD_REVISION}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/app/src PATH=/opt/venv/bin:$PATH MODEL_DIR=/models STORAGE_DIR=/var/lib/docucheck \
    OCR_PYTHON=/opt/venv/bin/python LLAMA_BINARY=/usr/local/bin/llama-server \
    BUILD_REVISION=${BUILD_REVISION} HOME=/var/lib/docucheck \
    TORCH_HOME=/var/lib/docucheck/cache/torch XDG_CACHE_HOME=/var/lib/docucheck/cache
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv libgl1 libglib2.0-0 libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv
WORKDIR /app
COPY requirements/web.lock requirements/inference.lock /app/requirements/
RUN pip install --no-cache-dir -r requirements/web.lock \
    && pip install --no-cache-dir --constraint requirements/web.lock --constraint requirements/inference.lock torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128 \
    && pip install --no-cache-dir --no-deps -r requirements/inference.lock
COPY --from=llama-build /llama/build/bin/llama-server /usr/local/bin/llama-server
COPY --from=llama-build /llama/LICENSE /app/licenses/llama.cpp-LICENSE
COPY src/ /app/src/
COPY configs/ /app/configs/
COPY scripts/serve_web.py /app/scripts/serve_web.py
COPY docs/DOCKER_HUB.md /app/DOCKER_HUB.md
RUN useradd --create-home --uid 10001 docucheck && mkdir -p /var/lib/docucheck && chown 10001:10001 /var/lib/docucheck
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=3s --start-period=60s --retries=3 CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]
CMD ["python", "scripts/serve_web.py", "--host", "0.0.0.0", "--port", "8000"]

# Docker Hub: --target bundled --build-context model_bundle=./models
# Named context includes only the explicit model files below, not source data.
FROM app AS bundled
COPY --from=model_bundle --chown=10001:10001 /manifest.json /SOURCES_AND_LICENSES.md /models/
COPY --from=model_bundle --chown=10001:10001 /qwen/model.gguf /models/qwen/model.gguf
COPY --from=model_bundle --chown=10001:10001 /phocr/ch_PP-OCRv5_server_det.onnx /models/phocr/ch_PP-OCRv5_server_det.onnx
COPY --from=model_bundle --chown=10001:10001 /vietocr/vgg_transformer.pth /vietocr/config.yml /models/vietocr/

# Default local/offline Compose keeps its existing external-model behavior.
FROM app AS runtime
