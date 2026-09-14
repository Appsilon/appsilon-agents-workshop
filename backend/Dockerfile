FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv sync
COPY . .
CMD ["uv", "run", "fastapi", "dev", "main.py", "--host", "0.0.0.0", "--reload-exclude", ".venv"]