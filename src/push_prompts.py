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
import argparse
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header, validate_prompt_structure

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
        # Criar ChatPromptTemplate a partir dos dados
        system_prompt = prompt_data.get('system_prompt', '')
        user_prompt = prompt_data.get('user_prompt', '{input}')
        
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("human", user_prompt))
        
        prompt_template = ChatPromptTemplate.from_messages(messages)
        
        # Metadados
        description = prompt_data.get('description', '')
        tags = prompt_data.get('tags', [])
        techniques = prompt_data.get('techniques_applied', [])
        if techniques:
            tags.extend(techniques)
        
        # Fazer push para o hub usando o cliente LangSmith diretamente
        client = Client()
        client.push_prompt(
            prompt_identifier=prompt_name,
            object=prompt_template,
            is_public=True,
            tags=tags,
            description=description
        )
        
        print(f"✅ Prompt '{prompt_name}' enviado com sucesso para o LangSmith Hub")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar prompt '{prompt_name}': {e}")
        return False


def validate_prompt(prompt_data: dict, is_original: bool = False) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt
        is_original: Se True, ignora a validação de técnicas aplicadas

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    is_valid, errors = validate_prompt_structure(prompt_data)
    
    if is_original:
        # Se for original, removemos o erro de falta de técnicas aplicadas
        errors = [e for e in errors if "técnicas requeridas" not in e]
        is_valid = len(errors) == 0
        
    return is_valid, errors


def main():
    parser = argparse.ArgumentParser(description="Push prompts para o LangSmith Hub")
    parser.add_argument("--original", action="store_true", help="Utilizar a versão v1 (original) em vez da v2")
    args = parser.parse_args()

    print_section_header("PUSH PROMPTS PARA LANGSMITH HUB")
    
    # Verificar variáveis de ambiente
    required_vars = ['LANGSMITH_API_KEY']
    if not check_env_vars(required_vars):
        sys.exit(1)
    
    # Carregar prompts do arquivo YAML
    version = "v1" if args.original else "v2"
    prompt_file = f"prompts/bug_to_user_story_{version}.yml"
    data = load_yaml(prompt_file)
    
    if not data:
        print(f"❌ Erro ao carregar arquivo: {prompt_file}")
        sys.exit(1)
    
    # Processar cada prompt no arquivo
    success_count = 0
    total_count = len(data)
    
    for prompt_name, prompt_data in data.items():
        print(f"\n📤 Processando prompt: {prompt_name}")
        
        # Validar prompt
        is_valid, errors = validate_prompt(prompt_data, is_original=args.original)
        if not is_valid:
            print("❌ Validação falhou:")
            for error in errors:
                print(f"   - {error}")
            continue
        
        # Fazer push
        if push_prompt_to_langsmith(prompt_name, prompt_data):
            success_count += 1
    
    print_section_header("RESUMO")
    print(f"Total de prompts processados: {total_count}")
    print(f"Prompts enviados com sucesso: {success_count}")
    print(f"Prompts com falha: {total_count - success_count}")
    
    if success_count == total_count:
        print("🎉 Todos os prompts foram enviados com sucesso!")
    else:
        print("⚠️ Alguns prompts falharam. Verifique os logs acima.")


if __name__ == "__main__":
    sys.exit(main())
