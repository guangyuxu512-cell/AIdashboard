FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    UVICORN_HOST=127.0.0.1 \
    UVICORN_PORT=18000

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN python -m pip install --no-cache-dir .

USER app

EXPOSE 18000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=4 \
    CMD ["python", "-c", "import json,os,urllib.request; p=os.environ.get('UVICORN_PORT','18000'); r=urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=2); assert r.status == 200 and json.load(r)['status'] == 'ok'"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--workers", "1", "--no-access-log"]
