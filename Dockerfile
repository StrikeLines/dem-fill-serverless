FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

# Basic setup
WORKDIR /workspace

# System dependencies (GDAL + image libraries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libspatialindex-dev \
        libopencv-dev \
        python3-opencv \
        unzip \
        wget \
        git && \
    rm -rf /var/lib/apt/lists/*

# Set GDAL environment for rasterio/GDAL compatibility
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV GDAL_DATA=/usr/share/gdal

# --- GitHub token build arg (if repo is private) ---
ARG GITHUB_TOKEN
ENV GITHUB_TOKEN=${GITHUB_TOKEN}

# Clone dem-fill repo into /workspace/shared/dem-fill
RUN mkdir -p /workspace/shared && \
    cd /workspace/shared && \
    if [ -n "$GITHUB_TOKEN" ]; then \
        git clone https://StrikeLines:${GITHUB_TOKEN}@github.com/StrikeLines/dem-fill.git; \
    else \
        git clone https://github.com/StrikeLines/dem-fill.git; \
    fi

WORKDIR /workspace/shared/dem-fill

# Download pretrained model 
RUN mkdir -p /workspace/shared/dem-fill/pretrained && \
    cd /workspace/shared/dem-fill/pretrained && \
    wget --no-check-certificate \
        'https://drive.usercontent.google.com/download?id=1bgOoUduXz62M03OxOOV0WK1J7ylsgnYR&export=download&confirm=t&uuid=1c4eb783-6126-4132-9796-f35705b4d482' \
        -O 20.zip && \
    unzip 20.zip && \
    rm 20.zip

# Install Python requirements
RUN pip install --no-cache-dir -r /workspace/shared/dem-fill/requirements.txt

# Install additional packages needed for serverless handler
RUN pip install --no-cache-dir boto3 runpod

# Copy serverless handler into the image
COPY handler.py /workspace/handler.py

# Default command for Runpod serverless
WORKDIR /workspace
CMD ["python", "handler.py"]