FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# Build tooling is needed to compile some wheels but adds ~250MB to the image, so
# it is removed once the install is done.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependencies are copied on their own so a source change does not invalidate the
# pip layer.
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential gcc

COPY app /workspace/app

RUN mkdir -p /workspace/data /workspace/models_checkpoint /workspace/logs

EXPOSE 8000

# Startup only reconciles the schema and loads whatever model artifacts exist, so
# the container answers its health check immediately. Seeding the catalogue and
# training are explicit steps:
#   python -m app.pipeline.ingest
#   python -m app.pipeline.enrich enrich
#   python -m app.ml.train
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/system/health', timeout=4).status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
