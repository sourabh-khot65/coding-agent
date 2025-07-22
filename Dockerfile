# Minimal coding agent container
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install only essential packages
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    nodejs npm \
    git \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Jupyter (optional)
RUN pip3 install jupyter

# Copy and install agent
WORKDIR /app
COPY agent/requirements.txt ./
RUN pip3 install -r requirements.txt
COPY agent/ .

# Setup workspace
RUN mkdir -p /workspace

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose Jupyter port
EXPOSE 8888

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"] 