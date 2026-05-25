import requests
import time
from typing import Dict, Any

# Configurações da API do SeuRastreio
API_KEY = "sr_live_3S4CWtiUlTeeU9AAaJ4LCJTyGiHQVHxQlIQd-6eXo8Y"
API_URL_BASE = "https://seurastreio.com.br/api/public/rastreio"

def fetch_tracking_data(object_code: str) -> Dict[str, Any]:
    """
    Consulta as informações de rastreio de um objeto utilizando a API externa do SeuRastreio.
    """
    code = object_code.strip().upper()
    url = f"{API_URL_BASE}/{code}"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Realiza a requisição GET para o endpoint do SeuRastreio
            # Aumentamos o timeout para 60 segundos por tentativa
            response = requests.get(url, headers=headers, timeout=60)
            
            # Lança erro se a resposta HTTP não for bem-sucedida (4xx ou 5xx)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2) # Espera 2 segundos antes de tentar novamente
                continue
            return {"error": "Serviço Temporariamente Lento", "message": "O servidor de rastreio não respondeu após várias tentativas (Timeout). O sistema dos Correios pode estar fora do ar."}
            
        except requests.exceptions.RequestException as e:
            try:
                # Se o erro for 429 (Too Many Requests) ou 5xx, podemos tentar de novo
                status_code = getattr(e.response, 'status_code', None)
                if status_code in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {"error": "Erro na API Externa", "message": response.json().get("message", str(e))}
            except:
                return {"error": f"Erro ao consultar serviço de rastreio: {str(e)}"}