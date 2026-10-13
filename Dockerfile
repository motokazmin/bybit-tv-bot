FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY contracts ./contracts
COPY app ./app
COPY infra ./infra
COPY tools ./tools
COPY bootstrap.py main.py ./

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
