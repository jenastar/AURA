FROM python:3.10-slim
RUN pip install prometheus-client==0.19.0 requests==2.31.0
WORKDIR /app
COPY exporter.py .
CMD ["python", "exporter.py"]
