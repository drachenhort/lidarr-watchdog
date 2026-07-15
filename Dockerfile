# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist


FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 watchdog

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

ENV LIDARR_WATCHDOG_DB_PATH=/config/lidarr-watchdog.db
ENV PUID=1000
ENV PGID=1000
RUN mkdir -p /config && chown watchdog:watchdog /config
VOLUME ["/config"]

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["lidarr-watchdog"]
