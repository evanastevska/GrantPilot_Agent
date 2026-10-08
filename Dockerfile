FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#cloud run sets PORT env var, gunicorn binds to it
#1 worker + 2 threads is fine for 1-2 users
#timeout 120s covers any slow individual request
CMD exec gunicorn --bind :$PORT --workers 1 --threads 2 --timeout 120 app:flask_app