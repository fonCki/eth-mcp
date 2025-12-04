# ETH VVZ MCP Server
# Self-contained container with scraper, MCP server, and pre-scraped database
# Auto-refreshes when new semesters become available

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# ============================================================================
# Docker Hub Labels (OCI Image Spec)
# ============================================================================
LABEL org.opencontainers.image.title="ETH VVZ MCP Server"
LABEL org.opencontainers.image.description="Unofficial MCP server for querying ETH Zurich course catalog. Community-built tool with pre-loaded database for instant use."
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.vendor="Alfonso Ridao"
LABEL org.opencontainers.image.authors="Alfonso Ridao"
LABEL org.opencontainers.image.url="https://hub.docker.com/r/alfonsoridao/eth-mcp"
LABEL org.opencontainers.image.source="https://github.com/alfonsoridao/eth-mcp"
LABEL org.opencontainers.image.documentation="https://github.com/alfonsoridao/eth-mcp#readme"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.base.name="ghcr.io/astral-sh/uv:python3.13-bookworm-slim"

# Custom labels
LABEL eth.semester.included="2026S"
LABEL mcp.protocol.version="1.0"

WORKDIR /app

# ============================================================================
# System Dependencies
# ============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Clone and Install vvzapi Scraper
# ============================================================================
RUN git clone --depth 1 https://github.com/markbeep/vvzapi.git /app/vvzapi

WORKDIR /app/vvzapi
RUN uv sync

# Create scrapy cache directory
RUN mkdir -p /app/vvzapi/.scrapy

# ============================================================================
# Install MCP Server
# ============================================================================
WORKDIR /app
RUN uv pip install --system mcp

# ============================================================================
# Copy Application Files
# ============================================================================
COPY entrypoint.py /app/entrypoint.py
COPY mcp_server.py /app/mcp_server.py
RUN chmod +x /app/entrypoint.py

# ============================================================================
# Pre-scraped Database (for instant startup)
# This gets copied to /data on first run if volume is empty
# ============================================================================
RUN mkdir -p /app/default-data /data

# Copy pre-scraped database (added during build)
# If db/ directory exists in build context, copy it
COPY db/ /app/default-data/

# ============================================================================
# Runtime Configuration
# ============================================================================
VOLUME /data

# Environment variables
ENV ETH_SEMESTER=""
ENV FORCE_REFRESH=""
ENV SCRAPE_UPCOMING="1"

# MCP server runs on stdio
ENTRYPOINT ["python", "/app/entrypoint.py"]
