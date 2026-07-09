"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)
"""

import os
import sys
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header

load_dotenv()

PROMPT_FILE = "prompts/bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def _unwrap(data: dict) -> dict:
    """Desembrulha a chave de topo do YAML, se existir."""
    if isinstance(data, dict) and PROMPT_KEY in data:
        return data[PROMPT_KEY]
    return data


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt.

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    errors = []

    if not isinstance(prompt_data, dict):
        return False, ["Estrutura do YAML inválida (esperado um dicionário)"]

    system_prompt = (prompt_data.get("system_prompt") or "").strip()
    user_prompt = (prompt_data.get("user_prompt") or "").strip()

    if not system_prompt:
        errors.append("system_prompt está vazio")
    if "TODO" in system_prompt:
        errors.append("system_prompt ainda contém TODO")
    if not user_prompt:
        errors.append("user_prompt está vazio")
    if "{bug_report}" not in user_prompt:
        errors.append("user_prompt deve conter a variável {bug_report}")

    techniques = prompt_data.get("techniques_applied", [])
    if len(techniques) < 2:
        errors.append(
            f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}"
        )

    return (len(errors) == 0, errors)


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt (ex.: 'bug_to_user_story_v2')
        prompt_data: Dados do prompt lidos do YAML

    Returns:
        True se sucesso, False caso contrário
    """
    system_prompt = prompt_data["system_prompt"]
    user_prompt = prompt_data.get("user_prompt", "{bug_report}")

    # Monta o ChatPromptTemplate que será consumido por evaluate.py
    # (chain = prompt_template | llm, com input {"bug_report": ...})
    template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_prompt),
    ])

    techniques = prompt_data.get("techniques_applied", [])
    description = prompt_data.get("description", "")
    tags = prompt_data.get("tags", [])
    readme = (
        f"{description}\n\n"
        f"Técnicas aplicadas: {', '.join(techniques)}."
    )

    client = Client()

    def _push(is_public: bool) -> str:
        kwargs = dict(
            object=template,
            is_public=is_public,
            description=description,
            readme=readme,
        )
        try:
            return client.push_prompt(prompt_name, tags=tags, **kwargs)
        except TypeError:
            # Fallback para versões do langsmith sem o argumento 'tags'
            return client.push_prompt(prompt_name, **kwargs)

    try:
        url = _push(is_public=True)
        print(f"   ✓ Push concluído (PÚBLICO): {url}")
    except Exception as e:
        if "handle" in str(e).lower():
            # Workspace ainda não tem um LangChain Hub handle -> publica privado.
            print("   ⚠️  Seu workspace ainda não tem um handle público no LangSmith,")
            print("      então o prompt foi publicado como PRIVADO.")
            url = _push(is_public=False)
            print(f"   ✓ Push concluído (PRIVADO): {url}")
            print("      Para avaliar agora, use USERNAME_LANGSMITH_HUB=- no .env")
            print("      (o evaluate.py puxará '-/bug_to_user_story_v2').")
            print("      Para tornar público depois: crie um handle no LangSmith e refaça o push.")
        else:
            raise

    return True


def main() -> int:
    """Função principal"""
    print_section_header("PUSH DE PROMPTS OTIMIZADOS")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    data = load_yaml(PROMPT_FILE)
    if not data:
        print(f"❌ Não foi possível carregar o arquivo: {PROMPT_FILE}")
        return 1

    prompt_data = _unwrap(data)

    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("❌ Prompt inválido:")
        for err in errors:
            print(f"   - {err}")
        return 1

    print("✓ Prompt validado com sucesso.")
    print(f"Enviando '{PROMPT_KEY}' como PÚBLICO para o LangSmith Hub...\n")

    try:
        push_prompt_to_langsmith(PROMPT_KEY, prompt_data)
    except Exception as e:
        print(f"\n❌ Erro ao fazer push: {e}")
        print("\nVerifique:")
        print("- LANGSMITH_API_KEY está configurada corretamente no .env")
        print("- Você tem permissão para publicar prompts públicos no workspace")
        return 1

    username = os.getenv("USERNAME_LANGSMITH_HUB", "")
    print("\n✅ Push concluído com sucesso.")
    if username:
        print(f"   Handle público: {username}/{PROMPT_KEY}")
        print(f"   evaluate.py irá puxar: {username}/{PROMPT_KEY}")
        print(f"   Dashboard: https://smith.langchain.com/hub/{username}/{PROMPT_KEY}")
    else:
        print("   ⚠️  Configure USERNAME_LANGSMITH_HUB no .env para o evaluate.py funcionar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
