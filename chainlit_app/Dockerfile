# # Base image
# FROM python:3.12-slim

# # Set environment variables for better behavior
# ENV PYTHONUNBUFFERED=1 \
#     PIP_NO_CACHE_DIR=1 \
#     PYTHONDONTWRITEBYTECODE=1

# # Set working directory
# WORKDIR /chainlit_app

# # Install system dependencies
# # These are minimal dependencies; modify as needed for your app.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc libpq-dev curl \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*

# # Copy only the requirements first to leverage Docker cache
# COPY requirements.txt .

# # Install Python dependencies
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the application code
# COPY ./ /chainlit_app/

# # Expose the port Chainlit will run on
# EXPOSE 8000

# # Command to run Chainlit
# CMD ["python", "-m", "chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]

# Base image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /chainlit_app

# Force HTTPS via apt config (works regardless of sources.list format)
RUN echo 'Acquire::https::Verify-Peer "false";' > /etc/apt/apt.conf.d/99https && \
    echo 'Acquire { https::Verify-Peer false; }' >> /etc/apt/apt.conf.d/99https && \
    printf 'Types: deb\nURIs: https://deb.debian.org/debian\nSuites: trixie trixie-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: https://deb.debian.org/debian-security\nSuites: trixie-security\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' > /etc/apt/sources.list.d/debian.sources && \
    apt-get update -o Acquire::Retries=10 && \
    apt-get install -y --no-install-recommends --fix-missing \
        gcc libpq-dev curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /chainlit_app/

EXPOSE 8000

CMD ["python", "-m", "chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]