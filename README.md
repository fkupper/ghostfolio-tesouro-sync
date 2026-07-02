# Tesouro Direto to Ghostfolio Sync 🇧🇷👻

Um script em Python dockerizado que sincroniza automaticamente os preços e históricos do **Tesouro Direto** (via Tesouro Transparente/CKAN) diretamente para a sua instância do **Ghostfolio**.

Como o Ghostfolio não suporta ativos brasileiros sem ticker internacional de forma nativa, este script automatiza a atualização de preços baseada na marcação a mercado oficial do Governo Federal, dispensando o uso de APIs pagas.

## 🚀 Como funciona?

O script roda em background através de um container Docker (usando o `cron` do Linux). De segunda a sexta-feira, ele:
1. Conecta-se à sua instância do Ghostfolio e autentica via API.
2. Procura ativos manuais que tenham um **padrão específico no campo Symbol** (ou definidos via arquivo de mapeamento).
3. Busca a URL dinâmica e baixa a planilha oficial atualizada do Tesouro Direto 
4. Processa os dados de compra e traduz as nomenclaturas.
5. Envia o histórico limpo para o Ghostfolio.

---

## ⚙️ Configurando no Ghostfolio 

Para que o script saiba quais títulos atualizar, você deve criar os ativos manualmente no Ghostfolio seguindo um padrão rígido de nomenclatura no campo **Symbol**. Como o Ghostfolio não aceita espaços ou caracteres especiais, usamos pontos e traços:

**Formato exigido:**
`TD.TIPO_DO_TITULO.DD-MM-YYYY`

*(Nota: O Ghostfolio adicionará automaticamente o prefixo `GF_` ao salvar. Não se preocupe, o script lida com isso automaticamente).*

**Passo a passo:**
1. Vá em `Admin > Market Data` no seu Ghostfolio.
2. Adicione um novo ativo com `Data Source: MANUAL`.
3. Defina a classe (`BOND`) e a moeda (`BRL`).
4. No campo **Symbol**, insira a string no formato exigido. Para espaços no nome do título, use o *underline* (`_`). 

**Exemplos reais:**
* Tesouro Selic 2027: `TD.LFT.01-03-2027`
* Tesouro IPCA+ 2045: `TD.NTN-B_Principal.15-05-2045`

**Tabela de Tipos de Títulos:**
* Tesouro Selic = `LFT`
* Tesouro IPCA+ = `NTN-B_Principal`
* Tesouro IPCA+ com Juros Semestrais = `NTN-B`
* Tesouro Prefixado = `LTN`
* Tesouro Prefixado com Juros Semestrais = `NTN-F`

---

## 🔄 Mantendo Ativos Antigos (mapping.json)

Se você **já possui** ativos do Tesouro Direto cadastrados manualmente no seu Ghostfolio com nomes próprios (ex: `GF_Minha_Reserva`), você não precisa deletá-los e perder seu histórico de transações!

Basta criar um arquivo chamado `mapping.json` na mesma pasta do seu `docker-compose.yml` e mapear o seu nome antigo para a estrutura lógica do script.

**Exemplo de `mapping.json`:**

```json
{
  "GF_Meu_Tesouro_IPCA": "TD.NTN-B_Principal.15-05-2045",
  "GF_Reserva_Emergencia": "TD.LFT.01-03-2027"
}
```

---

## 🐳 Instalação (Docker Compose)

Você pode rodar este sincronizador junto com a sua stack do Ghostfolio (ou separadamente) usando o `docker-compose.yml`.

1. Pegue a URL do seu Ghostfolio e seu token de acesso
2. Crie a pasta `data_cache` e o arquivo `mapping.json` (opcional).
3. Use o arquivo `docker-compose.yml` abaixo:

```yaml
version: '3.8'

services:
  tesouro-ghostfolio:
    image: ghcr.io/fkupper/ghostfolio-tesouro-sync
    container_name: tesouro-ghostfolio-sync
    restart: unless-stopped
    environment:
      - GHOSTFOLIO_URL=http://seu-ip-ou-dominio:3333
      - GHOSTFOLIO_TOKEN=seu_security_token_de_acesso
      - TZ=America/Sao_Paulo
    #volumes:
      # Opcional: cache local para evitar baixar os arquivos do tesouro repetidas vezes no mesmo dia caso necessario rodar novamente
      # - ./data_cache:/app/cache
      # Opcional: Arquivo para vincular nomes customizados existentes ao padrão do script
      # - ./mapping.json:/app/mapping.json
```

4. Execute o container:

```bash
docker compose up -d
```

O container ficará rodando silenciosamente e executará a sincronização todos os dias úteis durante a noite (horário em que as taxas do mercado já fecharam).