# FastAPI backend image for the Garment E-commerce Platform.
# Runs a long-lived uvicorn process (unlike Vercel serverless), so the
# lifespan migrations in app/main.py execute normally on startup.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first for better layer caching. All listed packages ship
# manylinux wheels (pg8000 is pure-Python, so no libpq/compiler needed).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code
COPY . .

# uvicorn listens on 8000 inside the container; map it to host :80 at run time
# (docker run -p 80:8000 ...). CloudFront fronts this over HTTP and adds HTTPS.
EXPOSE 8000

# 2 workers is comfortable on a t3.micro (1 GB). Raise on a bigger instance.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
