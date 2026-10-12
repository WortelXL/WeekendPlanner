FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    TZ=Europe/Amsterdam

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY static ./static

VOLUME /data
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/health')" || exit 1

# 1 worker + threads: SQLite en de sessiesleutel blijven zo eenvoudig en consistent
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:80", "--access-logfile", "-", "app:app"]
