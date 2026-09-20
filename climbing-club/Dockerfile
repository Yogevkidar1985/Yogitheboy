FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY run.py .
ENV PYTHONUNBUFFERED=1 CLUB_HOST=0.0.0.0 CLUB_PORT=8000 CLUB_DATA_DIR=/app/data
VOLUME ["/app/data"]
EXPOSE 8000
CMD ["python", "run.py"]
