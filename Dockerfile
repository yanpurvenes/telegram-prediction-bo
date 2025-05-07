FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Передаём переменные окружения в контейнер (Railway подставит значения)
ENV TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
ENV ADMIN_IDS=${ADMIN_IDS}

CMD ["python", "main.py"]
