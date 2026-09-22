FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY wms_agent ./wms_agent
ENV PYTHONUNBUFFERED=1
# adk web = dev UI, fine for the POC demo (keep the service private)
CMD ["sh", "-c", "adk web --host 0.0.0.0 --port ${PORT:-8080}"]
