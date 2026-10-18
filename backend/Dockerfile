FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    UVICORN_HOST=127.0.0.1 \
    UVICORN_PORT=18000

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home-dir /app app \
    && install -d -o app -g app /app/data/assets

COPY pyproject.toml ./

# The manifest is the single dependency source. Source-only changes must not
# invalidate dependency resolution/downloads; cache wheels for manifest changes.
RUN --mount=type=cache,id=control-center-backend-pip,target=/root/.cache/pip,sharing=locked \
    python -c 'import subprocess, sys, tomllib; data = tomllib.load(open("pyproject.toml", "rb")); subprocess.check_call([sys.executable, "-m", "pip", "install", *data["project"]["dependencies"], *data["build-system"]["requires"]])'

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Build the updated project with the declared, already-installed build backend.
# Any unexpected build download fails instead of silently depending on a network.
RUN --network=none python -m pip install --no-deps --no-build-isolation .

USER app

EXPOSE 18000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=4 \
    CMD ["python", "-c", "import json,os,urllib.request; p=os.environ.get('UVICORN_PORT','18000'); r=urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=2); assert r.status == 200 and json.load(r)['status'] == 'ok'"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--workers", "1", "--no-access-log"]
