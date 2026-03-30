FROM python:3.12-slim

ARG BUILD_ARCH=unknown
ARG BUILD_VERSION=dev

LABEL \
  io.hass.type="addon" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.arch="${BUILD_ARCH}"

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  APP_STORAGE_DIR=/data \
  PORT=5000 \
  CHROME_BINARY=/usr/bin/chromium

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    ca-certificates \
    fonts-dejavu-core \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/schiedsrichter_browser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.sh /run.sh

RUN chmod a+x /run.sh

EXPOSE 5000

CMD ["/run.sh"]
