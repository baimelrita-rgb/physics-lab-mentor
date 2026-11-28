# Lab mentor: one container with the API and the built web app.
# Build:  docker build -t lab-mentor .
# Local:  docker run -p 8000:8000 -v lab-state:/app/var -e DEMO=1 -e COOKIE_SECURE=0 lab-mentor
# Cloud:  see deploy/ (HTTPS in front, nightly backups, secrets from an env file).
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.13-slim
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PYTHONUNBUFFERED=1 STATE_DIR=/app/var/state
WORKDIR /app
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt
COPY apps/api/lab apps/api/lab
COPY content content
COPY data data
COPY tools/add_teacher.py tools/add_station.py tools/org.py tools/backup.py tools/
COPY --from=web /web/dist apps/web/dist
# The server runs as an unprivileged user; sessions, lessons, accounts and logs live in /app/var.
RUN chmod -R a+rX /app/apps /app/content /app/data /app/tools \
 && useradd --system --uid 10001 --home /app lab && mkdir -p /app/var/state /app/var/backups && chown -R lab /app/var
USER lab
VOLUME /app/var
WORKDIR /app/apps/api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
# One worker: sessions are kept in memory and written through to SQLite (see docs: scaling).
CMD ["python", "-m", "uvicorn", "lab.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
