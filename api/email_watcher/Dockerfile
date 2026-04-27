FROM python:3.13-slim

WORKDIR /app

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements (use parent api requirements)
COPY ../requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy main script
COPY main.py .

# Run the email watcher
CMD ["python", "main.py"]
