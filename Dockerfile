FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "my_digital_brain.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
