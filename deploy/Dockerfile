FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-inter curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY engine/requirements.txt engine/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r engine/requirements.txt
COPY . .
ENV STUDIO_MODELS=/models STUDIO_DATA=/data PORT=8787
VOLUME ["/models", "/data"]
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs localhost:8787/health || exit 1
CMD ["sh", "-c", "STUDIO_MODELS=/models scripts/download_models.sh && cd engine && python -m studio.supervisor"]
