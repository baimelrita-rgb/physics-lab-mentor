# Lab mentor: one container with the API and the built web app.
# Build:  docker build -t lab-mentor .
# Run:    docker run -p 8000:8000 -v lab-state:/app/var -e ANTHROPIC_API_KEY=... lab-mentor
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt
COPY apps/api/lab apps/api/lab
COPY content content
COPY data data
COPY --from=web /web/dist apps/web/dist
# Sessions, lessons and the learning log live here; mount a volume to keep them.
VOLUME /app/var
WORKDIR /app/apps/api
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "lab.app:app", "--host", "0.0.0.0", "--port", "8000"]
