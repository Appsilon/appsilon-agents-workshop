FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends make curl \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv sync
COPY . .
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--reload", "--reload-exclude", ".venv"]