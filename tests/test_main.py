from unittest.mock import patch, mock_open

from main import (
    obter_url_csv_atualizada, 
    CKAN_PACKAGE_ID,
    autenticar_ghostfolio,
    obter_ativos_tesouro_ghostfolio,
    GHOSTFOLIO_URL
)

def test_obter_url_csv_atualizada_sucesso(requests_mock):
    """Testa se a função extrai a URL corretamente quando a API responde com sucesso"""
    
    api_url = f"https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id={CKAN_PACKAGE_ID}"
    
    mock_resposta_governo = {
        "result": {
            "resources": [
                {"format": "JSON", "url": "http://ignorado.com"},
                {"format": "CSV", "url": "https://gov.br/planilha_falsa.csv"}
            ]
        }
    }
    
    requests_mock.get(api_url, json=mock_resposta_governo)
    
    url_resultado = obter_url_csv_atualizada()
    
    assert url_resultado == "https://gov.br/planilha_falsa.csv"

def test_obter_url_csv_atualizada_sem_csv(requests_mock):
    """Testa se a função retorna None caso não exista um arquivo CSV no pacote"""
    
    api_url = f"https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id={CKAN_PACKAGE_ID}"
    
    mock_resposta_sem_csv = {
        "result": {
            "resources": [
                {"format": "PDF", "url": "http://doc.pdf"}
            ]
        }
    }
    
    requests_mock.get(api_url, json=mock_resposta_sem_csv)
    
    url_resultado = obter_url_csv_atualizada()
    
    assert url_resultado is None

@patch("main.GHOSTFOLIO_TOKEN", "meu_token_secreto")
def test_autenticar_ghostfolio_sucesso(requests_mock):
    """Testa se a autenticação funciona de primeira e retorna o token JWT"""
    url_auth = f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous"
    
    requests_mock.post(url_auth, json={"authToken": "jwt_token_valido"}, status_code=201)
    
    token = autenticar_ghostfolio()
    
    assert token == "jwt_token_valido"
    assert requests_mock.last_request.json() == {"accessToken": "meu_token_secreto"}

@patch("main.time.sleep") 
def test_autenticar_ghostfolio_falha_total(mock_sleep, requests_mock):
    """Testa se o script desiste graciosamente após falhar 5 vezes"""
    url_auth = f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous"
    
    requests_mock.post(url_auth, text="Bad Gateway", status_code=502)
    
    token = autenticar_ghostfolio()
    
    assert token is None
    assert requests_mock.call_count == 5
    assert mock_sleep.call_count == 4

def test_obter_ativos_tesouro_ghostfolio(requests_mock):
    """Testa a extração e desmontagem das strings dos ativos do Ghostfolio"""
    url_ativos = f"{GHOSTFOLIO_URL}/api/v1/asset-profiles"
    
    mock_resposta_ativos = {
        "assetProfiles": [
            {"symbol": "AAPL"}, 
            {"symbol": "GF_TD.NTN-B_Principal.15-05-2029"}, 
            {"symbol": "TD.LFT.01-03-2027"}
        ]
    }
    
    requests_mock.get(url_ativos, json=mock_resposta_ativos, status_code=200)
    
    ativos_resultado = obter_ativos_tesouro_ghostfolio("jwt_token_falso")
    
    assert len(ativos_resultado) == 2
    
    assert ativos_resultado[0]["symbol_original"] == "GF_TD.NTN-B_Principal.15-05-2029"
    assert ativos_resultado[0]["tipo_titulo"] == "NTN-B Principal" 
    assert ativos_resultado[0]["data_vencimento"] == "15/05/2029" 
    
    assert ativos_resultado[1]["tipo_titulo"] == "LFT"
    assert ativos_resultado[1]["data_vencimento"] == "01/03/2027"

@patch("os.path.exists")
def test_obter_ativos_com_mapping_json(mock_exists, requests_mock):
    """Testa se o script lê o mapping.json e traduz nomes customizados corretamente"""
    
    mock_exists.return_value = True
    
    conteudo_falso_json = '{"GF_Reserva_De_Emergencia": "TD.LFT.01-03-2027"}'
    
    url_ativos = f"{GHOSTFOLIO_URL}/api/v1/asset-profiles"
    mock_resposta_ativos = {
        "assetProfiles": [
            {"symbol": "GF_Reserva_De_Emergencia"}
        ]
    }
    requests_mock.get(url_ativos, json=mock_resposta_ativos, status_code=200)
    
    with patch("builtins.open", mock_open(read_data=conteudo_falso_json)) as mock_file:
        ativos_resultado = obter_ativos_tesouro_ghostfolio("jwt_token_falso")
        
        mock_file.assert_any_call("/app/mapping.json", "r")
    
    assert len(ativos_resultado) == 1
    
    assert ativos_resultado[0]["symbol_original"] == "GF_Reserva_De_Emergencia" 
    
    assert ativos_resultado[0]["tipo_titulo"] == "LFT"
    assert ativos_resultado[0]["data_vencimento"] == "01/03/2027"