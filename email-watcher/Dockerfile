FROM python:3.11.9-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN pip install --no-cache-dir pymongo python-slugify python-dotenv httpx

COPY . .

CMD ["python", "main.py"]
