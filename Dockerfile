# MOVICO API image.
#
# The catalogue and the trained models are baked in at build time rather than
# mounted or seeded at runtime, because the target is a free-tier container with
# no persistent disk: anything written after the image is built is lost on the
# next deploy and on every wake from idle. They arrive from a release asset --
# see scripts/fetch_artifacts.py for why they are not in the repository.

FROM python:3.11-slim AS artifacts

# Fetching in its own stage means the ~172 MB download is one cached layer keyed
# on the URL, and none of the tooling used to unpack it reaches the final image.
#
# Render translates every service environment variable into a Docker build
# argument, but a build argument only exists if the Dockerfile declares an ARG for
# it -- and anything it does declare is recorded in the image's build history,
# readable by anyone who can pull the image. So exactly two are declared here, and
# both are public by nature: a release asset URL and its checksum. SECRET_KEY,
# DATABASE_URL, TMDB_API_KEY and ADMIN_TOKEN are deliberately absent; they reach
# the process as runtime environment variables and never touch a layer.
ARG ARTIFACTS_URL=""
ARG ARTIFACTS_SHA256=""

WORKDIR /artifacts
COPY scripts/fetch_artifacts.py /tmp/fetch_artifacts.py
RUN mkdir -p /artifacts/data /artifacts/models_checkpoint \
    && python /tmp/fetch_artifacts.py \
        --url "${ARTIFACTS_URL}" \
        --sha256 "${ARTIFACTS_SHA256}" \
        --destination /artifacts \
        --optional


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
COPY scripts /workspace/scripts

RUN mkdir -p /workspace/data /workspace/models_checkpoint /workspace/logs

COPY --from=artifacts /artifacts/data /workspace/data
COPY --from=artifacts /artifacts/models_checkpoint /workspace/models_checkpoint

# Run as an unprivileged user. A container process that does not need to write to
# its own code should not be able to, and root in a container is one namespace
# escape away from root on the host.
RUN useradd --create-home --uid 10001 movico \
    && chown -R movico:movico /workspace/data /workspace/models_checkpoint /workspace/logs
USER movico

EXPOSE 8000

# Startup only reconciles the schema and loads the baked-in model artifacts, so
# the container answers its health check in a couple of seconds. Rebuilding the
# catalogue and retraining are offline steps that produce a new release asset:
#   python -m app.pipeline.ingest
#   python -m app.pipeline.enrich enrich
#   python -m app.ml.train
#   python -m scripts.package_artifacts
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/system/health', timeout=4).status==200 else 1)"

# One worker is deliberate. The model artifacts occupy ~250 MB of resident memory
# and are not shared between processes, so a second worker would exceed a 512 MB
# instance before serving a single request. Concurrency comes from async handlers
# and the thread pool the numeric work is dispatched to.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
