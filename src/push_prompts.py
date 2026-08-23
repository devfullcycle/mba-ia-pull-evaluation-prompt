import os
import sys

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client

from utils import check_env_vars, load_yaml, print_section_header

load_dotenv()

PROMPT_FILE = "prompts/bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def validate_prompt(prompt_data: dict) -> tuple[bool, list[str]]:
    """Valida os campos necessários para publicar o prompt."""
    errors = []

    required_fields = ["description", "system_prompt", "user_prompt", "version"]
    for field in required_fields:
        if not str(prompt_data.get(field, "")).strip():
            errors.append(f"Campo obrigatório vazio ou ausente: {field}")

    techniques = prompt_data.get("techniques_applied", [])
    if not isinstance(techniques, list) or len(techniques) < 2:
        errors.append("Informe pelo menos duas técnicas em techniques_applied")

    return len(errors) == 0, errors


def build_chat_prompt(prompt_data: dict) -> ChatPromptTemplate:
    """Monta o ChatPromptTemplate a partir do YAML local."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", prompt_data["system_prompt"]),
            ("user", prompt_data["user_prompt"]),
        ]
    )


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """Publica o prompt otimizado no LangSmith Prompt Hub."""
    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("Prompt inválido:")
        for error in errors:
            print(f"- {error}")
        return False

    prompt_template = build_chat_prompt(prompt_data)
    tags = list(prompt_data.get("tags", []))
    tags.extend([prompt_data["version"], "mba"])

    readme = (
        f"{prompt_data['description']}\n\n"
        "Técnicas aplicadas:\n"
        + "\n".join(f"- {technique}" for technique in prompt_data.get("techniques_applied", []))
    )

    try:
        client = Client()
        url = client.push_prompt(
            prompt_name,
            object=prompt_template,
            is_public=True,
            description=prompt_data["description"],
            readme=readme,
            tags=tags,
        )
        print(f"Prompt publicado: {url}")
        return True
    except Exception as exc:
        print(f"Erro ao publicar '{prompt_name}': {type(exc).__name__}: {exc}")
        return False


def main():
    print_section_header("PUSH DE PROMPT OTIMIZADO")

    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        return 1

    prompts = load_yaml(PROMPT_FILE)
    if not prompts or PROMPT_KEY not in prompts:
        print(f"Prompt '{PROMPT_KEY}' não encontrado em {PROMPT_FILE}")
        return 1

    username = os.getenv("USERNAME_LANGSMITH_HUB")
    prompt_name = f"{username}/{PROMPT_KEY}"

    return 0 if push_prompt_to_langsmith(prompt_name, prompts[PROMPT_KEY]) else 1


if __name__ == "__main__":
    sys.exit(main())
