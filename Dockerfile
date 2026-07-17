# Orchestrator worker image (workers/orchestrator.py).
# Runs workflows + persistence activities only — game-driving activities
# execute on the HOST worker (they need the real desktop session).
FROM debian:bookworm-slim

# Install system dependencies
# - ca-certificates: required for uv to download Python and packages securely
# - build-essential, linux-libc-dev: required to compile evdev from source
# - libgl1, libglib2.0-0: required for opencv-python import-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    linux-libc-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv from the official container
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment variables to optimize uv builds and set a public Python toolchain path
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Create virtual environment and sync dependencies
# (uv will download its optimized CPython 3.14 automatically)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --python 3.14

# Copy application source
COPY . .

# Final sync and permissions adjustment:
# - Create log/stats dirs and set permissions
# - Make the Python installation globally readable so user 1000:1000 can access it
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --python 3.14 \
    && mkdir -p logs stats \
    && chmod 777 logs stats \
    && chmod -R 755 /opt/uv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    PYTHON_JIT=1 \
    # belt & braces: pynput is only imported lazily on the host paths, but
    # if anything ever pulls it in here, the dummy backend keeps it headless-safe
    PYNPUT_BACKEND=dummy

CMD ["python", "workers/orchestrator.py"]

