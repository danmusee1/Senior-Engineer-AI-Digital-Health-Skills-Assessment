Docker Build Fixes — Documentation
Root Cause
The Debian package mirror (deb.debian.org) was intermittently refusing plain HTTP (port 80) connections with 403 errors from the WSL/Docker environment on Windows. Every FROM stage that runs apt-get needs its own fix since each stage starts fresh.

1. Chainlit Dockerfile (chainlit_app/Dockerfile)
Problem: Used python:3.12-slim (Debian trixie) which stores apt sources in /etc/apt/sources.list.d/ not /etc/apt/sources.list, and had no HTTPS or retry config.
Fix: Replace the apt sources via DEB822 format and force HTTPS with retries:
dockerfile# BEFORE
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# AFTER
RUN printf 'Types: deb\nURIs: https://deb.debian.org/debian\nSuites: trixie trixie-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: https://deb.debian.org/debian-security\nSuites: trixie-security\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' > /etc/apt/sources.list.d/debian.sources && \
    apt-get update -o Acquire::Retries=10 && \
    apt-get install -y --no-install-recommends --fix-missing \
        gcc libpq-dev curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

2. Backend Dockerfile (backend/Dockerfile) — Second Stage
Problem: The build stage already had the HTTPS fix, but the second FROM stage (stage-1) still used plain apt-get update with no HTTPS fix, causing it to fail on ffmpeg and libpq5.
Fix: Add the same HTTPS + retry fix to the second stage:
dockerfile# BEFORE (second FROM stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# AFTER (second FROM stage)
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list && \
    apt-get update -o Acquire::Retries=10 && \
    apt-get install -y --no-install-recommends --fix-missing \
        ffmpeg \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

Key Lessons
IssueFixHTTP blocked by CDN (403)Switch to HTTPS in apt sourcessources.list not foundNewer Debian uses /etc/apt/sources.list.d/*.sources (DEB822 format)Intermittent download failuresAdd --fix-missing and -o Acquire::Retries=10Multi-stage buildsEvery FROM block needs its own apt fix — fixes don't carry over between stages


//checking for logs
# Check all at once
docker compose -p assessment logs --tail=50

# Or per service if you see issues
docker compose -p assessment logs backend --tail=50
docker compose -p assessment logs chainlit --tail=50
docker compose -p assessment logs frontend --tail=50
docker compose -p assessment logs relational_db --tail=50