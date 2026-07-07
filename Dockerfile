# Orchestrator worker image (workers/orchestrator.py).
# Runs workflows + persistence activities only — game-driving activities
# execute on the HOST worker (they need the real desktop session).
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# gcc/linux headers: evdev builds from source (imported by activity modules
# through the workflow sandbox, never actually opens a device here).
# libgl1/libglib2.0-0: opencv-python import-time runtime deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential linux-libc-dev libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_PREFERENCE=only-system

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev \
    # writable at runtime for the non-root compose user (logs/ is written by
    # the logger; stats/ is normally shadowed by the bind mount)
    && mkdir -p logs stats && chmod 777 logs stats

ENV PATH="/app/.venv/bin:$PATH" \
    # belt & braces: pynput is only imported lazily on the host paths, but
    # if anything ever pulls it in here, the dummy backend keeps it headless-safe
    PYNPUT_BACKEND=dummy

CMD ["python", "workers/orchestrator.py"]
