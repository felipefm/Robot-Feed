"""
Módulo de Roteamento LLM - Cascata Inteligente de APIs de IA
Responsável pela lógica de integração com múltiplos provedores de IA.
"""

import os
import logging
import re
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


# ========== FUNÇÕES AUXILIARES ==========

def read_system_prompt_from_file(file_name: str = "prompt.txt") -> str:
    """
    Lê um prompt de sistema de um arquivo local, com fallback para prompt padrão.
    
    Args:
        file_name: Nome do arquivo de prompt (relativo ao diretório raiz do projeto)
        
    Returns:
        Conteúdo do arquivo de prompt ou prompt padrão genérico
    """
    try:
        # Constrói o caminho relativo ao diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Vai dois níveis acima para chegar ao root do projeto
        root_dir = os.path.dirname(os.path.dirname(script_dir))
        file_path = os.path.join(root_dir, file_name)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning(f"Arquivo de prompt '{file_name}' não encontrado em {file_path}. Usando prompt padrão.")
        return "Processe os dados fornecidos de acordo com as melhores práticas."
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de prompt '{file_name}' em {file_path}: {e}. Usando prompt padrão.")
        return "Processe os dados fornecidos de acordo com as melhores práticas."


# ========== ROTEADOR LLM ==========

def call_llm_router(system_prompt: str, user_content: str) -> Dict[str, Any]:
    """
    Roteador Inteligente em Cascata: Tenta processar conteúdo usando múltiplas APIs em ordem de prioridade.
    
    Ordem de prioridade:
    1. LM STUDIO LOCAL (GPU Windows via Rede)
    2. GEMINI (Nuvem - Melhor para conteúdo muito longo)
    3. GROQ (Ultra rápido)
    4. DEEPSEEK (Excelente custo-benefício)
    5. MISTRAL (Reserva de segurança)
    
    Args:
        system_prompt: Diretrizes/instruções de como processar o conteúdo
        user_content: Dados de entrada a serem processados
        
    Returns:
        Dicionário com:
            - summary: Texto da resposta gerada
            - tokens_used: Número de tokens consumidos (se disponível)
            - provider: Nome do provedor utilizado
            
    Raises:
        ValueError: Se todas as opções falharem
    """
    full_content = f"Diretrizes:\n{system_prompt}\n\nDados:\n{user_content}"
    erros = []

    # 1. TENTATIVA 1: LM STUDIO LOCAL (GPU Windows via Rede)
    try:
        ollama_ip = os.getenv("OLLAMA_HOST_IP")
        ollama_model = os.getenv("OLLAMA_MODEL")
        
        if ollama_ip and ollama_model:
            # Porta 1234 é o padrão do LM Studio
            client = OpenAI(api_key="lm_studio_local", base_url=f"http://{ollama_ip}:1234/v1")
            response = client.chat.completions.create(
                model=ollama_model,
                messages=[{"role": "user", "content": full_content}],
                temperature=0.3
            )
            logger.info(f"Resposta gerada com sucesso pelo: LM STUDIO ({ollama_model})")
            return {
                "summary": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "provider": f"LM Studio ({ollama_model})"
            }
    except Exception as e:
        erros.append(f"Ollama Local (Erro: {e})")

    # 2. TENTATIVA 2: GEMINI (Nuvem - Melhor para conteúdo muito longo)
    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            from google import genai
            client = genai.Client(api_key=gemini_api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_content
            )
            logger.info("Resposta gerada com sucesso pelo: GEMINI")
            return {
                "summary": response.text,
                "tokens_used": (
                    response.usage_metadata.total_token_count 
                    if hasattr(response, 'usage_metadata') and response.usage_metadata 
                    else None
                ),
                "provider": "Gemini"
            }
    except Exception as e:
        erros.append(f"Gemini (Erro: {e})")

    # 3. TENTATIVA 3: GROQ (Ultra rápido)
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": full_content}],
                temperature=0.3
            )
            logger.info("Resposta gerada com sucesso pelo: GROQ")
            return {
                "summary": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "provider": "Groq"
            }
    except Exception as e:
        erros.append(f"Groq (Erro: {e})")

    # 4. TENTATIVA 4: DEEPSEEK (Excelente custo-benefício)
    try:
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_api_key:
            client = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_content}],
                temperature=0.3
            )
            logger.info("Resposta gerada com sucesso pelo: DEEPSEEK")
            return {
                "summary": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "provider": "DeepSeek"
            }
    except Exception as e:
        erros.append(f"DeepSeek (Erro: {e})")

    # 5. TENTATIVA 5: MISTRAL (Reserva de segurança)
    try:
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if mistral_api_key:
            client = OpenAI(api_key=mistral_api_key, base_url="https://api.mistral.ai/v1")
            response = client.chat.completions.create(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": full_content}],
                temperature=0.3
            )
            logger.info("Resposta gerada com sucesso pelo: MISTRAL")
            return {
                "summary": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "provider": "Mistral"
            }
    except Exception as e:
        erros.append(f"Mistral (Erro: {e})")

    # SE CHEGOU AQUI: Todas as chaves e o PC falharam
    detalhes_erro = " | ".join(erros)
    raise ValueError(
        f"FALHA GERAL: PC Local e todas as APIs da Nuvem falharam. Detalhes: {detalhes_erro}"
    )


# ========== PÓS-PROCESSAMENTO (ESPECÍFICO PARA YOUTUBE) ==========

def process_youtube_summary(summary: str, video_id: str) -> str:
    """
    Processa resumo específico para YouTube:
    1. Remove avisos padrão sobre geração de links
    2. Converte timestamps (MM:SS ou HH:MM:SS) em links clicáveis
    
    Args:
        summary: Texto do resumo bruto da IA
        video_id: ID do vídeo do YouTube
        
    Returns:
        Resumo processado com links clicáveis
    """
    # 1. Remover avisos sobre links
    disclaimer_pattern = r"(?i)\n*\*?\*?Observação sobre os links:?\*?\*?.*?(?=\n\n|\Z)"
    summary = re.sub(disclaimer_pattern, "", summary, flags=re.DOTALL)
    
    # 2. Converter timestamps em links
    def time_replacer(match):
        """Converte timestamp em link para o YouTube."""
        time_str = match.group(1)
        parts = time_str.split(':')
        try:
            secs = sum(int(x) * (60 ** i) for i, x in enumerate(reversed(parts)))
            return f"[{time_str}](https://youtu.be/{video_id}?t={secs})"
        except ValueError:
            return match.group(0)

    time_pattern = r'\[?(\b\d{1,2}:\d{2}(?::\d{2})?\b)\]?(?!\s*\()'
    summary = re.sub(time_pattern, time_replacer, summary)
    
    return summary.strip()
