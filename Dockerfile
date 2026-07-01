# Usa uma imagem oficial e leve do Python
FROM python:3.11-slim

# Instala o cron e limpa o cache do apt para manter a imagem pequena
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos necessários para dentro do contêiner
COPY requirements.txt /app/
COPY main.py /app/
COPY entrypoint.sh /app/

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Dá permissão de execução para o entrypoint
RUN chmod +x /app/entrypoint.sh

# Configura o Crontab
# Explicação do horário: 0 23 * * 1-5 (Roda às 23:00 UTC de Seg a Sex)
# Como servidores cloud geralmente rodam em UTC, 23h UTC = 20h no Brasil.
# Isso garante que o mercado já fechou e o CSV do governo foi atualizado.
RUN echo "0 23 * * 1-5 root /usr/local/bin/python /app/main.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/cron.d/tesouro_cron

# Aplica as permissões corretas no arquivo do cron
RUN chmod 0644 /etc/cron.d/tesouro_cron
RUN crontab /etc/cron.d/tesouro_cron

# Define o entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]