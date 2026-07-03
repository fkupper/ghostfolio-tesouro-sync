#!/bin/sh

# Extrai as variáveis de ambiente do Docker e as salva para o cron ler
printenv | grep -v "no_proxy" > /etc/environment

echo "================================================="
echo "🚀 Iniciando o container Tesouro -> Ghostfolio"
echo "================================================="

echo "▶️ Iniciando primeira execução imediata..."
python /app/main.py

echo "================================================="
echo "📅 Primeira execução concluída."
echo "⏳ Iniciando o agendador (cron) para rodar de Seg a Sex."
echo "================================================="

exec cron -f
