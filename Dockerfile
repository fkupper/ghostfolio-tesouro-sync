FROM python:3.11-slim

RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
COPY main.py /app/
COPY entrypoint.sh /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x /app/entrypoint.sh

RUN echo "0 23 * * 1-5 root /usr/local/bin/python /app/main.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/cron.d/tesouro_cron

RUN chmod 0644 /etc/cron.d/tesouro_cron
RUN crontab /etc/cron.d/tesouro_cron

ENTRYPOINT ["/app/entrypoint.sh"]