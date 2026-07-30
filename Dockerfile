FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl procps \
    && rm -rf /var/lib/apt/lists/*

# Copy docker CLI & docker-compose static binaries
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker/compose-bin:latest /docker-compose /usr/local/bin/docker-compose

# Copy uv binary for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
RUN uv pip install --system --no-cache -e .

COPY . .

EXPOSE 9999

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9999"]
