"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull dos prompts do Hub
3. Salva localmente em prompts/bug_to_user_story_v1.yml

SIMPLIFICADO: Usa serialização nativa do LangChain para extrair prompts.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain import hub
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

PROMPT_REPO = "leonanluppi/bug_to_user_story_v1"
OUTPUT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v1.yml"


def pull_prompts_from_langsmith() -> bool:
    """
    Faz pull do prompt leonanluppi/bug_to_user_story_v1 do LangSmith Hub
    e salva em prompts/bug_to_user_story_v1.yml.

    Returns:
        True se sucesso, False caso contrário
    """
    print_section_header(f"Fazendo pull do prompt: {PROMPT_REPO}")

    prompt = hub.pull(PROMPT_REPO)

    messages = prompt.messages
    system_prompt = ""
    user_prompt = ""

    for msg in messages:
        role = msg.__class__.__name__.lower()
        content = msg.prompt.template if hasattr(msg, "prompt") else str(msg)
        if "system" in role:
            system_prompt = content
        elif "human" in role:
            user_prompt = content

    prompt_key = PROMPT_REPO.split("/")[-1]
    data = {
        prompt_key: {
            "description": f"Prompt pulled from LangSmith Hub: {PROMPT_REPO}",
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "version": "v1",
            "source": PROMPT_REPO,
        }
    }

    success = save_yaml(data, str(OUTPUT_FILE))
    if success:
        print(f"Prompt salvo em: {OUTPUT_FILE}")
    return success


def main():
    """Função principal"""
    if not check_env_vars(["LANGCHAIN_API_KEY"]):
        return 1

    success = pull_prompts_from_langsmith()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
