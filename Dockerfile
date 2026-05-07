FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gdal-bin libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY data/ data/
COPY database/ database/

EXPOSE 7860

# Note: gunicorn runs the Dash server from app/main.py
CMD ["gunicorn", "--chdir", "app", "main:server", \
     "--bind", "0.0.0.0:7860", "--workers", "1", "--timeout", "120"]