import os
import pandas as pd
import requests
from datetime import datetime

# ==========================================
# 1. VARIÁVEIS DE AMBIENTE (Preparado para Docker)
# ==========================================
GHOSTFOLIO_URL = os.getenv("GHOSTFOLIO_URL", "http://localhost:3333").rstrip('/')
GHOSTFOLIO_TOKEN = os.getenv("GHOSTFOLIO_TOKEN")

# ID fixo do dataset do Tesouro Direto no portal de dados abertos
CKAN_PACKAGE_ID = "df56aa42-484a-4a59-8184-7676580c81e3"

def obter_url_csv_atualizada():
    """Consulta a API de dados abertos do governo para pegar a URL fresca do CSV"""
    print("🔍 Buscando a URL atualizada do Tesouro Direto via API CKAN...")
    api_url = f"https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id={CKAN_PACKAGE_ID}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        dados = response.json()
        
        # Procura o recurso que é um arquivo CSV
        for recurso in dados.get('result', {}).get('resources', []):
            if recurso.get('format', '').upper() == 'CSV':
                print("✅ URL do CSV encontrada!")
                return recurso['url']
                
        raise ValueError("Nenhum arquivo CSV encontrado no pacote do governo.")
    except Exception as e:
        print(f"❌ Erro ao buscar URL na API do governo: {e}")
        return None

def obter_ativos_tesouro_ghostfolio():
    """Busca no Ghostfolio todos os ativos que possuem o padrão TESOURO-IMPORT no Symbol"""
    print("🔍 Consultando ativos manuais no Ghostfolio...")
    endpoint = f"{GHOSTFOLIO_URL}/api/v1/admin/market-data"
    headers = {"Authorization": f"Bearer {GHOSTFOLIO_TOKEN}"}
    
    ativos_para_importar = []
    
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        
        # O Ghostfolio retorna um array de objetos Market Data ou encapsulado
        dados = response.json()
        lista_ativos = dados.get('marketData', dados) if isinstance(dados, dict) else dados
        
        for ativo in lista_ativos:
            symbol = ativo.get('symbol', '')
            
            # Padrão: TESOURO-IMPORT|TIPO|DD/MM/YYYY
            if symbol.startswith("TESOURO-IMPORT|"):
                partes = symbol.split("|")
                if len(partes) == 3:
                    ativos_para_importar.append({
                        "symbol_original": symbol,
                        "tipo_titulo": partes[1].strip(),
                        "data_vencimento": partes[2].strip()
                    })
                    
        print(f"✅ Encontrados {len(ativos_para_importar)} ativos para sincronizar.")
        return ativos_para_importar

    except Exception as e:
        print(f"❌ Erro ao comunicar com Ghostfolio: {e}")
        return []

def baixar_e_preparar_historico(url_csv):
    """Faz o download de todo o histórico do Tesouro"""
    print("⏳ Baixando base de dados do Tesouro Direto (~13MB)...")
    try:
        df = pd.read_csv(url_csv, sep=';', decimal=',')
        df['Data Referencia'] = pd.to_datetime(df['Data Referencia'], format='%d/%m/%Y')
        # Filtra apenas dados onde o Preço de Compra existe e é maior que zero
        df = df[df['PU Compra Manha'] > 0]
        return df
    except Exception as e:
        print(f"❌ Erro ao baixar ou processar a planilha: {e}")
        return None

def sincronizar_ativo(ativo_ghostfolio, df_historico_completo):
    """Filtra o CSV global para o ativo específico e envia ao Ghostfolio"""
    simbolo = ativo_ghostfolio['symbol_original']
    tipo = ativo_ghostfolio['tipo_titulo']
    vencimento = ativo_ghostfolio['data_vencimento']
    
    print(f"\n🔄 Processando: {simbolo}")
    
    filtro = (df_historico_completo['Tipo Titulo'] == tipo) & (df_historico_completo['Data Vencimento'] == vencimento)
    df_filtrado = df_historico_completo[filtro].sort_values(by='Data Referencia')
    
    if df_filtrado.empty:
        print(f"⚠️ Histórico não encontrado para {tipo} com vencimento em {vencimento}.")
        return

    market_data_payload = []
    for _, row in df_filtrado.iterrows():
        data_padrao = row['Data Referencia'].strftime('%Y-%m-%d')
        market_data_payload.append({
            "date": data_padrao,
            "marketPrice": float(row['PU Compra Manha'])
        })

    # Envio em lotes substitui o histórico do ativo
    endpoint = f"{GHOSTFOLIO_URL}/api/v1/admin/market-data/{simbolo}"
    headers = {
        "Authorization": f"Bearer {GHOSTFOLIO_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(endpoint, json={"marketData": market_data_payload}, headers=headers)

    if response.status_code in [200, 201]:
        print(f"✅ {len(market_data_payload)} dias de histórico sincronizados com sucesso!")
    else:
        print(f"❌ Falha na sincronização de {simbolo}: {response.status_code} - {response.text}")

# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    if not GHOSTFOLIO_TOKEN:
        print("❌ ERRO FATAL: Variável de ambiente GHOSTFOLIO_TOKEN não configurada.")
        exit(1)

    ativos_alvo = obter_ativos_tesouro_ghostfolio()
    
    if not ativos_alvo:
        print("Nenhum ativo padrão 'TESOURO-IMPORT|...' configurado no Ghostfolio. Encerrando.")
        exit(0)

    url_csv = obter_url_csv_atualizada()
    if url_csv:
        df_historico = baixar_e_preparar_historico(url_csv)
        
        if df_historico is not None:
            for ativo in ativos_alvo:
                sincronizar_ativo(ativo, df_historico)