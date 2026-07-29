FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    VALO_DATA_DIR=/data \
    PORT=8080

COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-prod.txt

COPY . .
RUN mkdir -p /data

EXPOSE 8080
CMD ["python", "run_prod.py"]
