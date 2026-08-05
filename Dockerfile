
# FROM python:3.11-slim-bookworm

# # Installations for build
# RUN apt-get update && apt-get install -y \
#     gdal-bin \
#     libgdal-dev \
#     g++ \
#     python3-dev \ 
#     && rm -rf /var/lib/apt/lists/*

# ENV GDAL_CONFIG=/usr/bin/gdal-config

# # Copy the uv binary from the official distroless Docker image
# COPY --from=ghcr.io/astral-sh/uv@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc /uv /uvx /bin/

# # Copy the project into the image
# COPY pyproject.toml uv.lock /app/


# # Disable development dependencies
# ENV UV_NO_DEV=1

# # Sync the project into a new environment, asserting the lockfile is up to date
# WORKDIR /app

# # Sync dependencies using --frozen instead of --locked
# RUN uv sync --frozen --no-dev --no-install-project
# COPY . /app/

# EXPOSE 8000
# CMD ["uv", "run", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]


FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_NO_DEV=1
ENV GDAL_CONFIG=/usr/bin/gdal-config

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc \
    /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal32 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY . /app/

EXPOSE 8000

CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]