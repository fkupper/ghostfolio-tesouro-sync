# Tesouro Direto to Ghostfolio Sync 🇧🇷👻

Um script em Python dockerizado que sincroniza automaticamente os preços e históricos do **Tesouro Direto** (via Tesouro Transparente/CKAN) diretamente para a sua instância do **Ghostfolio**.

Como o Ghostfolio não suporta ativos brasileiros sem ticker internacional de forma nativa, este script automatiza a atualização de preços baseada na marcação a mercado oficial do Governo Federal, dispensando o uso de APIs pagas.

## 🚀 Como funciona?

O script roda em background através de um contêiner Docker (usando o `cron` do Linux). De segunda a sexta-feira, ele:
1. Conecta-se à sua instância do Ghostfolio.
2. Procura ativos manuais que tenham uma **Tag específica no campo Symbol**.
3. Baixa a planilha oficial atualizada do Tesouro Direto.
4. Processa os dados de compra (PU Compra Manhã).
5. Envia o histórico limpo para o Ghostfolio.

## ⚙️ Configurando no Ghostfolio

Para que o script saiba quais títulos atualizar, você deve criar os ativos manualmente no Ghostfolio seguindo um padrão rígido de nomenclatura no campo **Symbol**:

`TESOURO-IMPORT|TIPO_DO_TITULO|DD/MM/YYYY`

**Passo a passo:**
1. Vá em `Admin > Market Data` no seu Ghostfolio.
2. Adicione um novo ativo com `Data Source: MANUAL`.
3. Defina a classe (`BOND`) e a moeda (`BRL`).
4. No campo **Symbol**, insira a string no formato exigido. Exemplo para um Tesouro IPCA+ 2045:
   `TESOURO-IMPORT|NTN-B Principal|15/05/2045`

**Tabela de Tipos (Nomenclatura Oficial do Governo):**
* Tesouro Selic = `LFT`
* Tesouro IPCA+ = `NTN-B Principal`
* Tesouro IPCA+ com Juros Semestrais = `NTN-B`
* Tesouro Prefixado = `LTN`
* Tesouro Prefixado com Juros Semestrais = `NTN-F`

## 🐳 Instalação (Docker Compose)

Você pode rodar este sincronizador junto com a sua stack do Ghostfolio (ou separadamente) usando o `docker-compose.yml`.

1. Crie um Security Token no seu Ghostfolio (Admin > Security > Security Token).
2. Use o arquivo `docker-compose.yml` abaixo:

```yaml
version: '3.8'

services:
  tesouro-ghostfolio:
    image: ghcr.io/seu-usuario/nome-do-repo:latest
    container_name: tesouro-ghostfolio-sync
    restart: unless-stopped
    environment:
      - GHOSTFOLIO_URL=http://seu-ip-ou-dominio:3333
      - GHOSTFOLIO_TOKEN=seu_security_token_gerado
      - TZ=America/Sao_Paulo