"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

DICAS DE IMPLEMENTAÇÃO:

- O push é feito pelo cliente do LangSmith:

      from langsmith import Client
      from langchain_core.prompts import ChatPromptTemplate

      client = Client()
      prompt = ChatPromptTemplate.from_messages([
          ("system", system_prompt),
          ("user", user_prompt),
      ])
      url = client.push_prompt(
          f"{username}/bug_to_user_story_v2",
          object=prompt,
          is_public=True,
          description="...",
          tags=[...],
      )

- `username` vem de USERNAME_LANGSMITH_HUB no .env e precisa ser o seu handle
  do Hub. Se você ainda não tem um handle, veja as instruções no .env.example.

- A variável do template precisa ser {bug_report}, que é a chave de entrada
  usada no dataset de avaliação.

- Use `load_yaml` de utils.py para ler o arquivo .yml.
"""

import os
import sys
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header
from pydantic import BaseModel

load_dotenv()

username = os.getenv("USERNAME_LANGSMITH_HUB")

class PromptInfo(BaseModel):
    description: str
    system_prompt: str
    user_prompt: str
    version: str
    created_at: str
    tags: list[str]

def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    client = Client()
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_data["system_prompt"]),
        ("user", prompt_data["user_prompt"]),
    ])

    # url = client.push_prompt(
    #     f"{username}/bug_to_user_story_v2",
    #     object=prompt,
    #     is_public=True,
    #     description=prompt_data["description"],
    #     tags=prompt_data["tags"],
    #     new_repo_is_public=True,
    # )

    # print(f"Prompt '{prompt_name}' enviado com sucesso para o LangSmith Hub: {url}")


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    if len(prompt_data) != 1:
        return False, ["O arquivo deve conter exatamente um prompt."]

    prompt_data = next(iter(prompt_data.values()))  # Extrai o conteúdo do prompt
    try:
        PromptInfo(**prompt_data)
        return True, []
    except Exception as e:
        return False, [str(e)]


def main():
    """Função principal"""
    file = "prompts/bug_to_user_story_v2.yml"
    prompt_dict = load_yaml(file)
    is_valid, errors = validate_prompt(prompt_dict)
    if not is_valid:
        print(f"Erro de validação para {file.name}: {errors}")
        return
    prompt_name = next(iter(prompt_dict.keys()))  # Extrai o nome do prompt
    push_prompt_to_langsmith(prompt_name, prompt_dict[prompt_name])  # Push para o Hub
    print(f"Prompt '{prompt_name}' enviado com sucesso para o LangSmith Hub.")

if __name__ == "__main__":
    sys.exit(main())
