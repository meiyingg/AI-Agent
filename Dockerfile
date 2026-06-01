# Backend (FastAPI + multi-agent + RAG) container — for Render / Railway / any Docker host.
# Frontend (web/) deploys separately to Vercel.
FROM python:3.12-slim

# ffmpeg = audio/video transcription (ASR). build tools not needed (wheels only).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (web/, data/store/, logs/ etc. are excluded via .dockerignore).
COPY . .

# Render/Railway inject $PORT; default 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# 0.0.0.0 so the container is reachable (the __main__ block binds 127.0.0.1 — local only).
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
