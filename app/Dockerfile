FROM python:3.11-slim

WORKDIR /app

COPY  requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app/app.py .
COPY app/recommender.py .
COPY src/reactiva ./reactiva

EXPOSE 5000

CMD ["uvicorn","app:app", "--host=0.0.0.0", "--port=5000"]