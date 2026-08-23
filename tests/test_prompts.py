"""
Testes automatizados para validação de prompts.
"""
import pytest
import yaml
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def prompt_data():
    """Carrega o prompt otimizado usado no desafio."""
    prompts = load_prompts(PROMPT_FILE)
    assert PROMPT_KEY in prompts
    return prompts[PROMPT_KEY]


@pytest.fixture(scope="session")
def prompt_text(prompt_data):
    """Retorna system e user prompt em uma única string para validações."""
    return "\n".join([
        prompt_data.get("system_prompt", ""),
        prompt_data.get("user_prompt", ""),
    ])


class TestPrompts:
    def test_prompt_has_system_prompt(self, prompt_data):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        assert prompt_data.get("system_prompt", "").strip()

        is_valid, errors = validate_prompt_structure(prompt_data)
        assert is_valid, errors

    def test_prompt_has_role_definition(self, prompt_text):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        text = prompt_text.lower()
        assert "product manager" in text
        assert "sênior" in text or "senior" in text

    def test_prompt_mentions_format(self, prompt_text):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        text = prompt_text.lower()
        assert "como um [persona]" in text
        assert "eu quero [necessidade]" in text
        assert "para que [benefício]" in text or "para que [beneficio]" in text
        assert "critérios de aceitação" in text or "criterios de aceitacao" in text

    def test_prompt_has_few_shot_examples(self, prompt_text):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        text = prompt_text.lower()
        assert "exemplo 1" in text
        assert "entrada:" in text
        assert "saída:" in text or "saida:" in text
        assert text.count("entrada:") >= 2
        assert text.count("saída:") + text.count("saida:") >= 2

    def test_prompt_no_todos(self, prompt_data):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        serialized = yaml.safe_dump(prompt_data, allow_unicode=True).lower()
        assert "[todo]" not in serialized
        assert "todo:" not in serialized

    def test_minimum_techniques(self, prompt_data):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = prompt_data.get("techniques_applied", [])
        assert isinstance(techniques, list)
        assert len(techniques) >= 2
        assert "Few-shot Learning" in techniques

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
