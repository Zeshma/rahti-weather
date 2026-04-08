FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN chmod -R 775 /app

CMD ["python", "app.py"]