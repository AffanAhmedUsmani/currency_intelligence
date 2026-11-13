FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Shell form (not exec-array form) so $PORT expands — Render/Railway/Fly inject their
# own PORT at runtime; falls back to 8000 for plain `docker run` / docker-compose.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
