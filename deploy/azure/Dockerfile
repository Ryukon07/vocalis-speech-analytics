FROM node:24-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=/api/v1 VITE_ARCHIVE_MODE=false VITE_PUBLIC_DEMO=true VITE_CLOUD_DEMO=true
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements.txt
COPY deploy/azure/runtime-requirements.txt deploy/azure/runtime-requirements.txt
RUN pip install --no-cache-dir torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r deploy/azure/runtime-requirements.txt
COPY . .
COPY --from=frontend /web/dist /app/static
RUN useradd --uid 10001 --create-home vocalis \
    && mkdir -p /state /models && chown vocalis:vocalis /state /models
USER 10001:10001
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend:/app/scripts \
    VOCALIS_PUBLIC_STATE=/state VOCALIS_FRONTEND_DIST=/app/static MODEL_CACHE_ROOT=/models \
    ANALYSIS_PROVIDER=evaluator ENABLE_DEMO_MODE=false CPU_THREADS=2 \
    ASR_MODEL=base.en TRANSCRIPTION_MODEL=medium TRANSCRIPTION_FALLBACK_MODEL=medium
EXPOSE 8000
CMD ["python", "-X", "faulthandler", "-m", "uvicorn", "public_demo_api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
