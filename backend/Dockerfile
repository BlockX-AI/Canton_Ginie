FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl gnupg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Eclipse Temurin JRE 17 (required by Daml SDK)
RUN curl -sSL https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor -o /usr/share/keyrings/adoptium.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb bookworm main" > /etc/apt/sources.list.d/adoptium.list && \
    apt-get update && apt-get install -y --no-install-recommends temurin-17-jre && \
    rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/temurin-17-jre-amd64

# Install Daml SDK (needed by compile_agent to run `daml build`)
# Uses direct GitHub tarball + retry to avoid transient network failures
ARG DAML_SDK_VERSION=2.10.4
RUN set -e && \
    SDK_URL="https://github.com/digital-asset/daml/releases/download/v${DAML_SDK_VERSION}/daml-sdk-${DAML_SDK_VERSION}-linux.tar.gz" && \
    echo "Downloading Daml SDK from: $SDK_URL" && \
    # Manual retry loop with resume (-C -) and HTTP/1.1 to avoid GitHub CDN
    # HTTP/2 PROTOCOL_ERROR drops on long (746MB) slow downloads.
    n=0; until [ $n -ge 8 ]; do \
      curl -SLf --http1.1 -C - \
        --connect-timeout 30 --max-time 1800 --speed-time 60 --speed-limit 1024 \
        "$SDK_URL" -o /tmp/daml-sdk.tar.gz && break; \
      n=$((n+1)); \
      echo "Download attempt $n failed, retrying in 15s..."; \
      sleep 15; \
    done && \
    test -s /tmp/daml-sdk.tar.gz && \
    mkdir -p /tmp/daml-sdk && \
    tar xzf /tmp/daml-sdk.tar.gz -C /tmp/daml-sdk --strip-components 1 && \
    /tmp/daml-sdk/install.sh && \
    rm -rf /tmp/daml-sdk /tmp/daml-sdk.tar.gz && \
    ln -sf /root/.daml/bin/daml /usr/local/bin/daml

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
