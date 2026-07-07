import os
import glob
import pandas as pd
import requests
import json
import time
from datetime import datetime

GHOSTFOLIO_URL = os.getenv("GHOSTFOLIO_URL", "http://localhost:3333").rstrip("/")
GHOSTFOLIO_TOKEN = os.getenv("GHOSTFOLIO_TOKEN")

# ID fixo do dataset do Tesouro Direto no portal de dados abertos
CKAN_PACKAGE_ID = "df56aa42-484a-4a59-8184-7676580c81e3"


def autenticar_ghostfolio():
    print("🔐 Autenticando no Ghostfolio...")
    url_auth = f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous"

    payload = {"accessToken": GHOSTFOLIO_TOKEN} if GHOSTFOLIO_TOKEN else {}

    max_tentativas = 5
    tempo_espera = 15  # segundos

    for tentativa in range(1, max_tentativas + 1):
        try:
            response = requests.post(url_auth, json=payload, timeout=10)

            if response.status_code in [200, 201]:
                print("✅ Autenticação bem-sucedida!")
                return response.json().get("authToken")

            erro_resumo = response.text[:100].replace("\n", " ")

            msg_aviso = f"Tentativa {tentativa}/{max_tentativas} falhou (Status {response.status_code}): {erro_resumo}..."
            print(f"⏳ {msg_aviso}")

        except requests.exceptions.RequestException as e:
            print(
                f"⏳ Tentativa {tentativa}/{max_tentativas} falhou por erro de conexão: {e}"
            )

        if tentativa < max_tentativas:
            print(f"   Aguardando {tempo_espera}s para o Ghostfolio iniciar...")
            time.sleep(tempo_espera)

    erro_fatal = "❌ Falha crítica: Não foi possível autenticar no Ghostfolio após várias tentativas. O servidor pode estar offline."
    notificar_erro(erro_fatal)
    return None


def obter_ativos_tesouro_ghostfolio(jwt_token):
    print("🔍 Consultando ativos manuais no Ghostfolio...")

    mapa_customizado = {}
    if os.path.exists("/app/mapping.json"):
        try:
            with open("/app/mapping.json", "r") as f:
                mapa_customizado = json.load(f)
            print(
                f"📄 Arquivo de mapeamento detectado! ({len(mapa_customizado)} regras locais)"
            )
        except Exception as e:
            notificar_erro(f"⚠️ Erro ao ler mapping.json: {e}")

    endpoint = f"{GHOSTFOLIO_URL}/api/v1/asset-profiles"
    headers = {"Authorization": f"Bearer {jwt_token}"}

    ativos_para_importar = []

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()

        dados = response.json()

        if isinstance(dados, dict):
            lista_ativos = dados.get("assetProfiles", dados.get("marketData", []))
        else:
            lista_ativos = dados

        for ativo in lista_ativos:
            symbol_original = ativo.get("symbol", "")
            symbol_limpo = symbol_original.replace("GF_", "")

            string_referencia = None

            if symbol_limpo.startswith("TD."):
                string_referencia = symbol_limpo
            elif symbol_original in mapa_customizado:
                string_referencia = mapa_customizado[symbol_original].replace("GF_", "")

            if string_referencia:
                partes = string_referencia.split(".")
                if len(partes) >= 3:
                    tipo_titulo = partes[1].replace("_", " ")
                    data_vencimento = partes[2].replace("-", "/")

                    ativos_para_importar.append(
                        {
                            "symbol_original": symbol_original,
                            "tipo_titulo": tipo_titulo,
                            "data_vencimento": data_vencimento,
                        }
                    )

        print(f"✅ Encontrados {len(ativos_para_importar)} ativos para sincronizar.")
        return ativos_para_importar

    except Exception as e:
        notificar_erro(f"❌ Erro ao comunicar com Ghostfolio: {e}")
        return []


def obter_url_csv_atualizada():
    """Consulta a API de dados abertos do governo para pegar a URL fresca do CSV"""
    print("🔍 Buscando a URL atualizada do Tesouro Direto via API CKAN...")
    api_url = f"https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id={CKAN_PACKAGE_ID}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        dados = response.json()

        for recurso in dados.get("result", {}).get("resources", []):
            if recurso.get("format", "").upper() == "CSV":
                print("✅ URL do CSV encontrada!")
                return recurso["url"]

        raise ValueError("Nenhum arquivo CSV encontrado no pacote do governo.")
    except Exception as e:
        notificar_erro(f"❌ Erro ao buscar URL na API do governo: {e}")
        return None


def baixar_e_preparar_historico(url_csv):
    """Faz o download e usa cache local para evitar múltiplos downloads. Preserva os 10 mais recentes."""
    pasta_cache = "/app/cache"
    os.makedirs(pasta_cache, exist_ok=True)

    hoje_str = datetime.now().strftime("%Y-%m-%d")
    arquivo_cache = os.path.join(pasta_cache, f"tesouro_{hoje_str}.csv")

    # 1. DOWNLOAD (ou uso do cache do dia)
    if os.path.exists(arquivo_cache):
        print(
            f"📦 Usando cache local: tesouro_{hoje_str}.csv (evitando download dos 13MB)"
        )
    else:
        print("⏳ Baixando base oficial do Tesouro Direto (~13MB)...")
        try:
            resposta = requests.get(url_csv, stream=True)
            resposta.raise_for_status()
            with open(arquivo_cache, "wb") as f:
                for chunk in resposta.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("✅ Download concluído e salvo no cache!")
        except Exception as e:
            notificar_erro(f"❌ Erro ao baixar a planilha: {e}")
            return None

    # 2. LIMPEZA (Rotina para manter apenas os 10 arquivos mais recentes preservados)
    arquivos_salvos = sorted(
        glob.glob(os.path.join(pasta_cache, "tesouro_*.csv")), key=os.path.getmtime
    )
    while len(arquivos_salvos) > 10:
        antigo = arquivos_salvos.pop(0)
        os.remove(antigo)
        print(
            f"🗑️ Limpeza de rotina: Removido cache antigo ({os.path.basename(antigo)})"
        )

    # 3. LEITURA COM PANDAS
    try:
        df = pd.read_csv(arquivo_cache, sep=";", decimal=",")

        df["Tipo Titulo"] = df["Tipo Titulo"].str.strip()
        df["Data Base"] = pd.to_datetime(df["Data Base"], format="%d/%m/%Y")
        df["Data Vencimento"] = pd.to_datetime(df["Data Vencimento"], format="%d/%m/%Y")
        df = df[df["PU Compra Manha"] > 0]
        return df
    except Exception as e:
        notificar_erro(f"❌ Erro ao processar a planilha do cache: {e}")
        return None


def sincronizar_ativo(ativo_ghostfolio, df_historico_completo, jwt_token):
    """Filtra o CSV global para o ativo específico e envia ao Ghostfolio"""
    simbolo = ativo_ghostfolio["symbol_original"]
    tipo = ativo_ghostfolio["tipo_titulo"].strip()
    vencimento_str = ativo_ghostfolio["data_vencimento"].strip()

    mapa_nomes = {
        "LFT": "Tesouro Selic",
        "NTN-B Principal": "Tesouro IPCA+",
        "NTN-B": "Tesouro IPCA+ com Juros Semestrais",
        "LTN": "Tesouro Prefixado",
        "NTN-F": "Tesouro Prefixado com Juros Semestrais",
    }

    tipo_no_csv = mapa_nomes.get(tipo, tipo)
    print(
        f"\n🔄 Processando: {simbolo} (Buscando por: '{tipo_no_csv}' | Venc: {vencimento_str})"
    )

    try:
        vencimento_dt = pd.to_datetime(vencimento_str, format="%d/%m/%Y")
    except Exception as e:
        notificar_erro(f"⚠️ Erro ao converter a data {vencimento_str}: {e}")
        return

    filtro = (df_historico_completo["Tipo Titulo"] == tipo_no_csv) & (
        df_historico_completo["Data Vencimento"] == vencimento_dt
    )
    df_filtrado = df_historico_completo[filtro].sort_values(by="Data Base")

    if df_filtrado.empty:
        notificar_erro(
            f"⚠️ Histórico não encontrado no Governo para '{tipo_no_csv}' com vencimento em {vencimento_str}."
        )
        return

    market_data_payload = []
    for _, row in df_filtrado.iterrows():
        data_padrao = row["Data Base"].strftime("%Y-%m-%d")
        market_data_payload.append(
            {"date": data_padrao, "marketPrice": float(row["PU Compra Manha"])}
        )

    endpoint = f"{GHOSTFOLIO_URL}/api/v1/market-data/MANUAL/{simbolo}"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        endpoint, json={"marketData": market_data_payload}, headers=headers
    )

    if response.status_code in [200, 201]:
        print(
            f"✅ {len(market_data_payload)} dias de histórico sincronizados com sucesso!"
        )
    else:
        notificar_erro(
            f"❌ Falha na sincronização de {simbolo}: {response.status_code} - {response.text}"
        )


def notificar_erro(mensagem):
    enviar_notificacao(mensagem, tipo="error")


def notificar_sucesso(mensagem):
    enviar_notificacao(mensagem, tipo="success")


def enviar_notificacao(mensagem, tipo="success"):
    """
    Envia uma notificação caso as variáveis de ambiente estejam configuradas.
    tipo: "error" (padrão) ou "success"
    """
    print(mensagem)
    if tipo == "success":
        notify_success_env = os.getenv("NOTIFY_SUCCESS", "false").lower()
        if notify_success_env != "true":
            return

    if tipo == "error":
        titulo = "Erro Sincronização Tesouro"
        prioridade = "high"
        tags_ntfy = "rotating_light,ghost"
        prefixo_msg = "🚨 *Erro no Tesouro-Ghostfolio:*\n"
        prefixo_msg_discord = "🚨 **Erro no Tesouro-Ghostfolio:**\n"
    else:
        titulo = "Sucesso Sincronização Tesouro"
        prioridade = "default"
        tags_ntfy = "white_check_mark,ghost"
        prefixo_msg = "✅ *Sucesso no Tesouro-Ghostfolio:*\n"
        prefixo_msg_discord = "✅ **Sucesso no Tesouro-Ghostfolio:**\n"

    # 1. Tentativa via Webhook (Discord, Slack, etc)
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        try:
            payload = {
                "content": f"{prefixo_msg_discord}{mensagem}",
                "text": f"{prefixo_msg}{mensagem}",
            }
            requests.post(webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Falha ao notificar via Webhook: {e}")

    # 2. Tentativa via Telegram
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {
                "chat_id": telegram_chat,
                "text": f"{prefixo_msg}{mensagem}",
                "parse_mode": "Markdown",
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Falha ao notificar via Telegram: {e}")

    # 3. Tentativa via ntfy
    ntfy_url = os.getenv("NTFY_URL")
    if ntfy_url:
        try:
            headers = {"Title": titulo, "Priority": prioridade, "Tags": tags_ntfy}
            ntfy_token = os.getenv("NTFY_TOKEN")
            if ntfy_token:
                headers["Authorization"] = f"Bearer {ntfy_token}"

            requests.post(
                ntfy_url, data=mensagem.encode("utf-8"), headers=headers, timeout=10
            )
        except Exception as e:
            print(f"⚠️ Falha ao notificar via ntfy: {e}")


# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    inicio_execucao = time.time()

    if not GHOSTFOLIO_TOKEN:
        print("❌ ERRO FATAL: Variável de ambiente GHOSTFOLIO_TOKEN não configurada.")
        exit(1)

    jwt_sessao = autenticar_ghostfolio()
    if not jwt_sessao:
        print("Encerrando execução por falha de autenticação.")
        exit(1)

    ativos_alvo = obter_ativos_tesouro_ghostfolio(jwt_sessao)
    if not ativos_alvo:
        print(
            "Nenhum ativo padrão 'TD.TIPO.DATA' configurado no Ghostfolio. Encerrando."
        )
        exit(0)

    url_csv = obter_url_csv_atualizada()
    if url_csv:
        df_historico = baixar_e_preparar_historico(url_csv)

        if df_historico is not None:
            for ativo in ativos_alvo:
                sincronizar_ativo(ativo, df_historico, jwt_sessao)

    fim_execucao = time.time()
    duracao_segundos = fim_execucao - inicio_execucao

    # Define a variável tempo_str corretamente antes de usar
    if duracao_segundos >= 60:
        minutos = int(duracao_segundos // 60)
        segundos = duracao_segundos % 60
        tempo_str = f"{minutos}m {segundos:.2f}s"
    else:
        tempo_str = f"{duracao_segundos:.2f} segundos"

    print("=================================================")
    print(f"⏱️ Tempo total de execução: {tempo_str}")
    print("=================================================")

    # Agora o Python sabe quem é o tempo_str!
    msg_sucesso = f"Sincronização concluída com sucesso em {tempo_str}."
    notificar_sucesso(msg_sucesso)
