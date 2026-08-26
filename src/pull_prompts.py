import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate

from utils import check_env_vars, print_section_header

load_dotenv()

PROMPT_HUB_ID = "leonanluppi/bug_to_user_story_v1"
OUTPUT_PATH = Path("prompts/bug_to_user_story_v1.yml")


def extract_prompt_templates(prompt: ChatPromptTemplate) -> tuple[str, str]:
    """Extrai os templates system e user de um ChatPromptTemplate."""
    system_prompt = ""
    user_prompt = ""

    for message in prompt.messages:
        template = getattr(getattr(message, "prompt", None), "template", "")
        message_type = type(message).__name__.lower()

        if "system" in message_type:
            system_prompt = template
        elif "human" in message_type:
            user_prompt = template

    return system_prompt, user_prompt


def build_prompt_yaml(prompt_name: str, prompt: ChatPromptTemplate) -> dict:
    """Monta a estrutura YAML usada pelo projeto."""
    system_prompt, user_prompt = extract_prompt_templates(prompt)

    return {
        prompt_name: {
            "description": "Prompt para converter relatos de bugs em User Stories",
            "system_prompt": LiteralString(system_prompt),
            "user_prompt": user_prompt,
            "version": "v1",
            "source": "LangSmith Prompt Hub",
            "source_prompt": PROMPT_HUB_ID,
            "tags": ["bug-analysis", "user-story", "product-management"],
        }
    }


class LiteralString(str):
    """Marca campos que devem ser gravados como bloco literal no YAML."""


def literal_string_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


def save_prompt_yaml(data: dict, output_path: Path) -> bool:
    """Salva YAML mantendo prompts multi-linha em formato legível."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        yaml.add_representer(LiteralString, literal_string_representer)

        with open(output_path, "w", encoding="utf-8") as file:
            yaml.dump(data, file, allow_unicode=True, sort_keys=False, indent=2)

        return True
    except Exception as exc:
        print(f"Erro ao salvar YAML em '{output_path}': {type(exc).__name__}: {exc}")
        return False


def pull_prompt_from_langsmith() -> bool:
    """Faz pull do prompt base do LangSmith Hub e salva no diretório local."""
    print_section_header("PULL DE PROMPTS DO LANGSMITH")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return False

    print(f"Baixando prompt: {PROMPT_HUB_ID}")

    try:
        prompt = hub.pull(PROMPT_HUB_ID)
        prompt_data = build_prompt_yaml(OUTPUT_PATH.stem, prompt)

        if not save_prompt_yaml(prompt_data, OUTPUT_PATH):
            return False

        print(f"Prompt salvo em: {OUTPUT_PATH}")
        return True
    except Exception as exc:
        print(f"Erro ao baixar '{PROMPT_HUB_ID}': {type(exc).__name__}: {exc}")
        return False


def main():
    """Função principal"""
    return 0 if pull_prompt_from_langsmith() else 1


if __name__ == "__main__":
    sys.exit(main())
