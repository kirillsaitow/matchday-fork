FROM python:3.12-slim

WORKDIR /app

# Ставим зависимости в системный Python, без venv: иначе папка с хоста,
# примонтированная в /app, затрёт виртуальное окружение.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
