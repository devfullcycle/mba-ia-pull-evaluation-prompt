"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

SIMPLIFICADO: Código mais limpo e direto ao ponto.
"""

import os
import sys
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header

load_dotenv()


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    try:
        from langsmith import Client

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt_data["system_prompt"]),
            ("human", prompt_data["user_prompt"]),
        ])

        tags = [f"v{prompt_data['version']}"]

        client = Client()
        url = client.push_prompt(
            prompt_name,
            object=prompt_template,
            tags=tags,
            description=prompt_data.get("description", ""),
            is_public=True,
        )
        print(f"✅ Prompt '{prompt_name}' publicado: {url}")
        return True
    except Exception as e:
        print(f"❌ Erro ao publicar '{prompt_name}': {e}")
        return False


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    errors = []
    for field in ["system_prompt", "user_prompt", "version"]:
        if field not in prompt_data:
            errors.append(f"Campo obrigatório faltando: {field}")
    return (len(errors) == 0, errors)


def main():
    """Função principal"""
    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    print_section_header("Push de Prompts para o LangSmith Hub")

    yaml_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "bug_to_user_story_v2.yml")
    data = load_yaml(yaml_path)
    if not data:
        return 1

    success = True
    for prompt_name, prompt_data in data.items():
        is_valid, errors = validate_prompt(prompt_data)
        if not is_valid:
            print(f"❌ Prompt '{prompt_name}' inválido: {errors}")
            success = False
            continue
        if not push_prompt_to_langsmith(prompt_name, prompt_data):
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
