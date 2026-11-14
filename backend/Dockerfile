FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.8
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY app ./app
COPY tests ./tests
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
