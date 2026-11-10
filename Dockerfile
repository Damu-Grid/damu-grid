FROM python:3.11-slim

ENV UV_PROJECT_ENVIRONMENT=/opt/damu-grid/.venv \
    PYTHONUNBUFFERED=1
WORKDIR /opt/damu-grid

RUN pip install --no-cache-dir uv==0.13.0
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend ./backend
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
