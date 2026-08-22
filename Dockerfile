# --- Stage 1: build the frontend ---
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: runtime ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY db.py server.py sync_articles.py migrate_to_sqlite.py download_am730_column.py ./
COPY articles.db ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENV HOST=0.0.0.0
EXPOSE 8420

ENTRYPOINT ["./docker-entrypoint.sh"]
