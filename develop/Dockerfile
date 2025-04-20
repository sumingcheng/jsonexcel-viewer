FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir pandas flask werkzeug openpyxl

EXPOSE 23333

CMD ["python", "main.py"]