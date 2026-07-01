#!/bin/bash

# Extrai as variáveis de ambiente do Docker e as salva para o cron ler
printenv | grep -v "no_proxy" > /etc/environment

echo "================================================="
echo "🚀 Iniciando o sincronizador Tesouro -> Ghostfolio"
echo "📅 Cronjob configurado para rodar de Seg a Sex."
echo "================================================="

# Inicia o cron em primeiro plano (foreground) para o Docker não desligar
exec cron -f