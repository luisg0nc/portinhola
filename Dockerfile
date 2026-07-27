FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE alembic.ini ./
COPY portinhola/ portinhola/
COPY alembic/ alembic/
RUN pip install --no-cache-dir -e . \
  && playwright install --with-deps chromium \
  && rm -rf /var/lib/apt/lists/*
COPY --from=frontend /build/build/ portinhola/frontend_dist/

ENV PORTINHOLA_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn portinhola.app:create_app --factory --host 0.0.0.0 --port 8000"]
