FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git docker.io docker-compose-v2 curl procps \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
RUN uv pip install --system --no-cache -e .

COPY . .

EXPOSE 9999

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9999"]
