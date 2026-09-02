FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/reactiva/pipeline/run_pipeline.py ./pipeline.py
COPY src/reactiva ./reactiva

CMD ["python", "pipeline.py"]