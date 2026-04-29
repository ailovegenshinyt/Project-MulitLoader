FROM python:3.10-slim

# Install FFmpeg and curl_cffi dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libnss3 \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create downloads directory
RUN mkdir -p downloads

# Expose port 7860 (HuggingFace standard)
EXPOSE 7860

CMD ["python", "app.py"]
