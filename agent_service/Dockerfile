FROM python:3.12-slim

WORKDIR /app
COPY agent_service/requirements.txt /app/agent_service/requirements.txt
RUN pip install --no-cache-dir -r agent_service/requirements.txt

COPY agent_service /app/agent_service
COPY catalog /app/catalog
COPY shared /app/shared

EXPOSE 8011
CMD ["uvicorn", "agent_service.api.main:app", "--host", "0.0.0.0", "--port", "8011"]
