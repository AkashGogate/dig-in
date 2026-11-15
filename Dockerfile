FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.8
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev
COPY backend/app ./app
COPY backend/tests/fixtures ./tests/fixtures
COPY backend/fixtures ./fixtures
# Import the CV lane's owning event contract without shipping camera libraries.
COPY cv-service/cvsvc/events.py ./cvsvc/events.py
COPY schema/events.schema.json ./schema/events.schema.json
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
