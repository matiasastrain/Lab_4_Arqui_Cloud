FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pdi ./pdi
COPY main.py .

# Usuario sin privilegios
RUN useradd --uid 10001 --no-create-home app
USER app

# Cloud Run entrega el puerto en $PORT (8080 por defecto)
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
