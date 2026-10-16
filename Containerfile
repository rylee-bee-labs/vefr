# ── vefr: a rumor engine for playable worlds ──────────────────
# Bundled brain edition — ships with llama.cpp + 4 small models.
# `docker compose up` = fully playable game, no external LLM setup.
#
# Override to external brain:
#   VEFR_LLAMACPP_URL=http://host.lan:8084 VEFR_MODEL=qwen3-1.7b podman run ...
# ──────────────────────────────────────────────────────────────

# ── Stage 1: build llama.cpp from source ──────────────────────
FROM ubuntu:24.04 AS llama-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl git ca-certificates && \
    rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch b5530 https://github.com/ggml-org/llama.cpp.git /build && \
    cd /build && \
    cmake -B build -DLLAMA_CURL=OFF -DLLAMA_SERVER=ON -DLLAMA_NATIVE=ON -DBUILD_SHARED_LIBS=OFF && \
    cmake --build build --config Release -j$(nproc) --target llama-server && \
    cp build/bin/llama-server /usr/local/bin/llama-server && \
    ldd /usr/local/bin/llama-server | grep "not found" && exit 1 || true && \
    /usr/local/bin/llama-server --version

# ── Stage 2: vefr engine ─────────────────────────────────────
FROM python:3.12-slim AS engine
WORKDIR /app
ENV VEFR_HOME=/app \
    VEFR_VAULT=/app/data/vault.json \
    VEFR_JOURNAL=/app/data/journal.json

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
# hatch_build.py is the hatch build hook: it joins web/player/parts/ into
# web/packaged.html before packaging, because that file is generated and
# never committed (vefr#523) and the wheel force-includes it as package data
# (weave's template). It has to be in the build context for `pip install .`.
COPY hatch_build.py ./hatch_build.py
# web/ must land BEFORE the install, and the hook reads the parts under it:
# the wheel force-includes the generated web/packaged.html, so the install
# needs web/player/ on disk. (Latent since the force-include landed; buildx
# cache hid it until an src change busted the layer.)
COPY web ./web
RUN pip install --no-cache-dir .
COPY worlds ./worlds-template
# The features catalog the studio's shelves read (GET /api/features). Just this one file:
# the rest of docs/ stays out of the image.
COPY docs/features.json ./docs/features.json

RUN mkdir -p /app/worlds /app/data
VOLUME ["/app/worlds-template", "/app/worlds", "/app/data"]

# ── Stage 3: bundled brain ───────────────────────────────────
FROM engine AS brain

# Copy llama-server from the builder stage
COPY --from=llama-builder /usr/local/bin/llama-server /usr/local/bin/llama-server
RUN llama-server --version
# Vision gate: the fleet promises a vision tenant on :8085, which needs
# multimodal (mtmd) support compiled in. Fail the build if it is missing.
RUN llama-server --help 2>&1 | grep -q -- "--mmproj" && \
    echo "multimodal (--mmproj) support: compiled in" || \
    { echo "FATAL: llama-server built without --mmproj (no vision)"; exit 1; }

# Download the model fleet (~2.7GB total).
# curl -L follows HuggingFace redirects; size checks catch error-page
# downloads (a bad URL returns a 15-29 byte page, never a model).
# One layer per model so editing one download never re-fetches the rest.
RUN mkdir -p /app/models
RUN echo "Downloading Qwen3-0.6B (spark)..." && \
    curl -sSL "https://huggingface.co/unsloth/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf" \
      -o /app/models/spark.gguf && \
    test $(stat -c%s /app/models/spark.gguf) -gt 100000000
RUN echo "Downloading Qwen3-1.7B (storyteller)..." && \
    curl -sSL "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf" \
      -o /app/models/storyteller.gguf && \
    test $(stat -c%s /app/models/storyteller.gguf) -gt 500000000
RUN echo "Downloading bge-m3 (embeddings)..." && \
    curl -sSL "https://huggingface.co/vonjack/bge-m3-gguf/resolve/main/bge-m3-q8_0.gguf" \
      -o /app/models/embeddings.gguf && \
    test $(stat -c%s /app/models/embeddings.gguf) -gt 300000000
# Vision: SmolVLM2's only official 500M checkpoint (Video-Instruct) at Q8_0
# + its multimodal projector. Image URLs API-verified 2026-09-22:
#   main    436,808,704 B   mmproj 108,785,184 B
RUN echo "Downloading SmolVLM2-500M (vision)..." && \
    curl -sSL "https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/SmolVLM2-500M-Video-Instruct-Q8_0.gguf" \
      -o /app/models/vision.gguf && \
    echo "Downloading SmolVLM2 vision projector (mmproj)..." && \
    curl -sSL "https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf" \
      -o /app/models/vision-mmproj.gguf && \
    test $(stat -c%s /app/models/vision.gguf) -gt 400000000 && \
    test $(stat -c%s /app/models/vision-mmproj.gguf) -gt 100000000
RUN echo "Model fleet:" && ls -lh /app/models/

# Entrypoint: start bundled brain + engine
COPY deploy/start-bundled.sh /app/start-bundled.sh
RUN chmod +x /app/start-bundled.sh

# Runs as container root ON PURPOSE — decision recorded in the commit that
# removed the non-root USER (2026-09-21). A non-root USER (uid 999) cannot
# write host-owned BIND MOUNTS under rootless engines (the documented
# default): host uid 1000 maps to container uid 0, so the mount appears
# root:root 755 and uid 999 gets EACCES — observed live as
# POST /api/rumor -> PermissionError: /app/data/journal.tmp.
# Under a rootless engine container root IS the unprivileged invoking user,
# so no real privilege is gained or lost there; under rootful engines this
# is the ordinary container contract. Named volumes are unaffected either way.
# Do NOT re-add USER without solving bind-mount ownership first.

# Bundled brain defaults (override with env vars for external brain)
# The image ships no Storyteller Packs, so VEFR_MODEL is the storyteller model here.
ENV VEFR_LLAMACPP_URL=http://127.0.0.1:8084 \
    VEFR_MODEL=qwen3-1.7b \
    VEFR_SPARK_URL=http://127.0.0.1:8083 \
    VEFR_VISION_URL=http://127.0.0.1:8085 \
    VEFR_EMBED_URL=http://127.0.0.1:8086 \
    VEFR_BUNDLED_BRAIN=1

ARG ENGINE_SHA=unknown
LABEL vefr.engine_sha=${ENGINE_SHA} \
      vefr.bundled_brain=1 \
      vefr.models="qwen3-0.6b,qwen3-1.7b,smolvlm2-500m,bge-m3"

CMD ["/app/start-bundled.sh"]
