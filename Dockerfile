# syntax=docker/dockerfile:1

FROM rust:1.83-slim AS rust-builder

WORKDIR /builder

COPY jmcomic-downloader/Cargo.toml jmcomic-downloader/Cargo.lock ./jmcomic-downloader/
COPY jmcomic-downloader/src ./jmcomic-downloader/src

RUN cd jmcomic-downloader \
    && cargo build --release \
    && cp target/release/jmcomic-downloader /builder/jmcomic-downloader-linux

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_SERVER_HOST=0.0.0.0 \
    WEB_SERVER_PORT=5000 \
    UMASK=000

WORKDIR /app

COPY requirements-web.txt ./

RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .

COPY --from=rust-builder /builder/jmcomic-downloader-linux ./bin/jmcomic-downloader-linux

RUN mkdir -p data download export

EXPOSE 5000

CMD ["python", "web_server.py"]

