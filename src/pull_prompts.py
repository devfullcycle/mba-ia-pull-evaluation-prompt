"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull dos prompts do Hub
3. Salva localmente em prompts/bug_to_user_story_v1.yml
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain import hub
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

# Prompt de baixa qualidade publicado no Hub e caminho de saída local
SOURCE_PROMPT = "leonanluppi/bug_to_user_story_v1"
OUTPUT_PATH = "prompts/bug_to_user_story_v1.yml"
PROMPT_KEY = "bug_to_user_story_v1"


def extract_messages(prompt) -> tuple[str, str]:
    """
    Extrai o texto de system e human de um prompt do LangChain.

    Suporta ChatPromptTemplate (com .messages) e PromptTemplate simples.

    Returns:
        (system_prompt, user_prompt)
    """
    system_text = ""
    user_text = ""

    messages = getattr(prompt, "messages", None)

    if messages:
        for msg in messages:
            template = getattr(getattr(msg, "prompt", None), "template", None)
            if template is None:
                # Ex.: MessagesPlaceholder — sem template textual
                continue

            cls = type(msg).__name__.lower()
            if "system" in cls:
                system_text = template
            elif "human" in cls or "user" in cls:
                user_text = template
    else:
        # PromptTemplate simples: todo o conteúdo vai para system_prompt
        system_text = getattr(prompt, "template", str(prompt))

    return system_text, user_text


def pull_prompts_from_langsmith() -> bool:
    """
    Faz pull do prompt v1 do LangSmith Hub e salva localmente em YAML.

    Returns:
        True se sucesso, False caso contrário
    """
    print(f"   Puxando prompt do Hub: {SOURCE_PROMPT}")

    prompt = hub.pull(SOURCE_PROMPT)
    system_text, user_text = extract_messages(prompt)

    if not system_text and not user_text:
        print("   ⚠️  Não foi possível extrair o conteúdo do prompt.")
        return False

    data = {
        PROMPT_KEY: {
            "description": "Prompt inicial de baixa qualidade puxado do LangSmith Hub.",
            "system_prompt": system_text,
            "user_prompt": user_text or "{bug_report}",
            "version": "v1",
            "source": SOURCE_PROMPT,
            "tags": ["bug-analysis", "user-story", "product-management"],
        }
    }

    if save_yaml(data, OUTPUT_PATH):
        print(f"   ✓ Prompt salvo em: {OUTPUT_PATH}")
        return True

    return False


def main() -> int:
    """Função principal"""
    print_section_header("PULL DE PROMPTS DO LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    try:
        ok = pull_prompts_from_langsmith()
    except Exception as e:
        print(f"\n❌ Erro ao fazer pull de '{SOURCE_PROMPT}': {e}")
        print("\nVerifique:")
        print("- LANGSMITH_API_KEY está configurada corretamente no .env")
        print("- Você tem conexão com a internet")
        print(f"- O prompt '{SOURCE_PROMPT}' existe e está público")
        return 1

    if ok:
        print("\n✅ Pull concluído com sucesso.")
        print("   Próximo passo: otimize o prompt em prompts/bug_to_user_story_v2.yml")
        return 0

    print("\n❌ Pull não foi concluído.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
