FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y docker.io
RUN pip install flask
RUN pip install requests

CMD ["python", "app.py"]