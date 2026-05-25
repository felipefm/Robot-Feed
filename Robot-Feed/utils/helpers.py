"""
utils/helpers.py - Funções auxiliares reutilizáveis
"""

from models import get_config


def get_api_url(api_type='youtube'):
    """
    Formata e retorna a URL base da API remota, removendo barras finais.
    
    Args:
        api_type (str): Tipo de API - 'youtube' para resumo ou 'auction' para leilões
    
    Returns:
        str: URL formatada da API (sem barra final)
    
    Exemplos:
        >>> get_api_url('youtube')
        'http://192.168.0.11:8000'
        
        >>> get_api_url('auction')
        'http://192.168.0.6:8000'
    """
    conf = get_config()
    
    if api_type == 'auction':
        url = conf.auction_api_url or 'http://192.168.0.6:8000'
    else:  # youtube (resumo)
        url = conf.youtube_api_url or "http://host.docker.internal:8000"
    
    # Remove barra final se existir
    return url.rstrip('/')


def format_url(url, **kwargs):
    """
    Formata uma URL com parâmetros nomeados.
    
    Args:
        url (str): Template da URL (ex: '{base}/endpoint')
        **kwargs: Parâmetros nomeados para substituição
    
    Returns:
        str: URL formatada
    
    Exemplos:
        >>> format_url('{base}/api/check-live/{channel_id}', 
        ...            base=get_api_url(), 
        ...            channel_id='UCxxxxx')
        'http://192.168.0.11:8000/api/check-live/UCxxxxx'
    """
    return url.format(**kwargs)


def build_api_endpoint(path, api_type='youtube'):
    """
    Constrói uma URL completa de endpoint da API.
    
    Args:
        path (str): Caminho relativo (ex: '/api/resumo' ou 'check-live/xxxxx')
        api_type (str): Tipo de API ('youtube' ou 'auction')
    
    Returns:
        str: URL completa formatada
    
    Exemplos:
        >>> build_api_endpoint('/api/resumo')
        'http://host.docker.internal:8000/api/resumo'
        
        >>> build_api_endpoint('/lotes', 'auction')
        'http://192.168.0.6:8000/lotes'
    """
    base_url = get_api_url(api_type)
    
    # Remove barra inicial do path se existir para evitar duplas
    if path.startswith('/'):
        path = path[1:]
    
    return f"{base_url}/{path}"
